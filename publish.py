"""게시 시간이 지난 게시물 중 가장 오래된 1개를 Instagram API로 올린다.

필요한 환경변수: IG_TOKEN (Instagram 로그인 사용자 액세스 토큰), GITHUB_REPOSITORY
이미지는 공개 저장소의 raw URL로 Instagram 서버가 직접 가져간다.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
POSTS = ROOT / "posts"
API = "https://graph.instagram.com"
TOKEN = os.environ.get("IG_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace").replace(TOKEN, "***")
        raise SystemExit(f"API error {e.code} on {path}: {body}")


def wait_ready(cid):
    for _ in range(30):
        st = call("GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise SystemExit(f"container {cid} status {st}")
        time.sleep(5)
    raise SystemExit(f"container {cid} not ready")


def due_post(now):
    for d in sorted(POSTS.iterdir()):
        pj = d / "post.json"
        if not pj.exists() or (d / "posted.json").exists() or not (d / "1.jpg").exists():
            continue
        post = json.loads(pj.read_text(encoding="utf-8"))
        if dt.datetime.fromisoformat(post["time"]) <= now:
            return d, post
    return None, None


def main():
    if not TOKEN:
        print("IG_TOKEN secret is missing - skipping until it is added")
        return
    now = dt.datetime.now(dt.timezone.utc)
    # 밀린 게시물이 한꺼번에 올라가지 않도록 최근 게시 후 3시간은 쉰다
    last = [dt.datetime.fromisoformat(json.loads(p.read_text(encoding="utf-8"))["posted_at"])
            for p in POSTS.glob("*/posted.json")]
    if last and now - max(last) < dt.timedelta(hours=3):
        print("posted recently, waiting")
        return
    d, post = due_post(now)
    if not d:
        print("no post due")
        return
    me = call("GET", "me", fields="user_id,username")
    ig = me["user_id"]
    n = len(post["slides"])
    urls = [f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/posts/{d.name}/{i}.jpg" for i in range(1, n + 1)]
    if n == 1:
        cid = call("POST", f"{ig}/media", image_url=urls[0], caption=post["caption"])["id"]
    else:
        kids = []
        for u in urls:
            kid = call("POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"]
            kids.append(kid)
        for kid in kids:
            wait_ready(kid)
        cid = call("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(kids),
                   caption=post["caption"])["id"]
    wait_ready(cid)
    res = call("POST", f"{ig}/media_publish", creation_id=cid)
    (d / "posted.json").write_text(json.dumps({"media_id": res.get("id"), "posted_at": now.isoformat(),
                                               "account": me.get("username")}, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print("published", d.name, res.get("id"))


if __name__ == "__main__":
    main()
