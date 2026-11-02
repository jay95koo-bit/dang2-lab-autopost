"""게시 시간이 지난 게시물 중 가장 오래된 1개를 Instagram API로 올린다.

필요한 환경변수: IG_TOKEN (Instagram 로그인 사용자 액세스 토큰), GITHUB_REPOSITORY
이미지는 공개 저장소의 raw URL로 Instagram 서버가 직접 가져간다.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import random
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
POSTS = ROOT / "posts"
API = "https://graph.instagram.com"
TOKEN = os.environ.get("IG_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")


class APIError(SystemExit):
    pass


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
        raise APIError(f"API error {e.code} on {path}: {body}")


def wait_ready(cid):
    for _ in range(30):
        st = call("GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise SystemExit(f"container {cid} status {st}")
        time.sleep(5)
    raise SystemExit(f"container {cid} not ready")


COMMENT = ("댕냥이 키우는 데 정말 유용한 정보만 드릴게요! 🐶🐱\n"
           "팔로우해 주시면 절대 실망시키지 않을게요 🙌\n"
           "도움이 됐다면 저장하고, 필요한 친구에게 공유해 주세요 💛")

KST = dt.timezone(dt.timedelta(hours=9))
SLOTS = [(12, 30), (20, 30)]  # 게시 시간대 (KST)
STALE = dt.timedelta(hours=6)  # 이보다 오래 밀린 게시물은 맨 뒤로 미룬다


def next_slot(after):
    t = after.astimezone(KST)
    for day in range(3):
        base = (t + dt.timedelta(days=day)).date()
        for h, m in SLOTS:
            c = dt.datetime(base.year, base.month, base.day, h, m, tzinfo=KST)
            if c > t:
                return c
    raise RuntimeError("no slot")


def reschedule_stale(now):
    """오래 밀린 게시물을 몰아 올리지 않도록 예약된 마지막 게시물 다음 시간대로 옮긴다."""
    pending = []
    for d in sorted(POSTS.iterdir()):
        pj = d / "post.json"
        if pj.exists() and not (d / "posted.json").exists():
            pending.append((d, json.loads(pj.read_text(encoding="utf-8"))))
    if not pending:
        return
    last = max(dt.datetime.fromisoformat(p["time"]) for _, p in pending)
    for d, post in pending:
        t = dt.datetime.fromisoformat(post["time"])
        if now - t <= STALE:
            continue
        last = next_slot(max(last, now))
        post["time"] = last.isoformat(timespec="seconds")
        (d / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
        suffix = d.name.split("-", 4)[4] if d.name.count("-") >= 4 else d.name
        new = POSTS / f"{last:%Y-%m-%d-%H%M}-{suffix}"
        if not new.exists():
            d.rename(new)
        print("rescheduled", d.name, "->", new.name, post["time"])


def due_post(now):
    for d in sorted(POSTS.iterdir()):
        pj = d / "post.json"
        if not pj.exists() or (d / "posted.json").exists() or not (d / "1.jpg").exists():
            continue
        post = json.loads(pj.read_text(encoding="utf-8"))
        if dt.datetime.fromisoformat(post["time"]) <= now:
            return d, post
    return None, None


COOLDOWN = ROOT / "state" / "cooldown.json"
BLOCK_PAUSE = dt.timedelta(hours=24)


def blocked(e):
    s = str(e)
    return "2207051" in s or "action is blocked" in s


def main():
    if not TOKEN:
        print("IG_TOKEN secret is missing - skipping until it is added")
        return
    now = dt.datetime.now(dt.timezone.utc)
    # Instagram이 활동을 제한하면(action is blocked) 계속 시도할수록 길어지므로 24시간 쉰다
    if COOLDOWN.exists():
        until = dt.datetime.fromisoformat(json.loads(COOLDOWN.read_text(encoding="utf-8"))["until"])
        if now < until:
            print(f"cooling down after Instagram action block until {until.isoformat()}")
            return
    reschedule_stale(now)
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
    # 매번 정각에 올라가지 않도록 1~12분 무작위로 기다린다 (POST_JITTER=0 이면 생략)
    jitter = random.randint(60, 720) if os.environ.get("POST_JITTER", "1") != "0" else 0
    print(f"posting {d.name} after {jitter}s")
    time.sleep(jitter)
    now = dt.datetime.now(dt.timezone.utc)
    me = call("GET", "me", fields="user_id,username")
    ig = me["user_id"]
    n = len(post["slides"])
    raw = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
    urls = [f"{raw}/posts/{d.name}/{i}.jpg" for i in range(1, n + 1)]
    # 맨 마지막 장에 저장·공유·팔로우 안내 카드를 붙인다 (캐러셀은 최대 10장)
    if (ROOT / "assets" / "cta.jpg").exists() and not post.get("no_cta") and n < 10:
        urls.append(f"{raw}/assets/cta.jpg")
        n += 1
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
    # 상태가 FINISHED여도 가끔 "Media ID is not available"(9007)이 나므로 잠시 후 다시 시도한다
    for attempt in range(6):
        try:
            res = call("POST", f"{ig}/media_publish", creation_id=cid)
            break
        except APIError as e:
            if blocked(e):
                COOLDOWN.parent.mkdir(exist_ok=True)
                COOLDOWN.write_text(json.dumps({"until": (now + BLOCK_PAUSE).isoformat(), "error": str(e)[:300]},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"::error::Instagram이 활동을 제한했어요. 24시간 쉬고 다시 시도해요: {e}")
                raise
            if '"code":9007' not in str(e) or attempt == 5:
                raise
            print("media not ready yet, retrying publish")
            time.sleep(20)
    info = {"media_id": res.get("id"), "posted_at": now.isoformat(), "account": me.get("username")}
    (d / "posted.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print("published", d.name, res.get("id"))
    # 첫 댓글로 팔로우 안내를 남긴다. 실패해도 게시는 이미 끝났으니 경고만 남긴다
    comment = post.get("comment", COMMENT)
    if comment and res.get("id"):
        try:
            info["comment_id"] = call("POST", f"{res['id']}/comments", message=comment).get("id")
            print("commented", info["comment_id"])
        except APIError as e:
            info["comment_error"] = str(e)[:300]
            print(f"::warning::댓글 달기 실패: {e}")
        (d / "posted.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
