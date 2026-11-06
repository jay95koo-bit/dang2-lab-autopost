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


# 자동 첫 댓글은 스팸으로 보일 수 있어 끈다 (post.json에 "comment"를 넣은 게시물만 단다)
COMMENT = ""

KST = dt.timezone(dt.timedelta(hours=9))
# 매일 같은 시각에 올리면 자동화로 보이기 쉬워서, 하루 1개를 이 시간대(KST) 안의 무작위 시각에 올린다
WINDOW = ((9, 0), (22, 0))
MIN_GAP = dt.timedelta(hours=16)  # 연달아 올리는 두 게시물 사이 최소 간격
STALE = dt.timedelta(hours=6)  # 이보다 오래 밀린 게시물은 맨 뒤로 미룬다


def random_time(day, not_before):
    """day(KST 날짜)의 게시 시간대 안에서 not_before 이후 무작위 시각. 넣을 자리가 없으면 None."""
    (h1, m1), (h2, m2) = WINDOW
    lo = dt.datetime(day.year, day.month, day.day, h1, m1, tzinfo=KST)
    hi = dt.datetime(day.year, day.month, day.day, h2, m2, tzinfo=KST)
    lo = max(lo, not_before.astimezone(KST))
    if lo >= hi:
        return None
    mins = int((hi - lo).total_seconds() // 60)
    t = lo + dt.timedelta(minutes=random.randint(1, max(mins, 1)))
    return t.replace(second=0, microsecond=0)


def next_slot(after, prev=None):
    """after 다음 날짜부터, 직전 게시물(prev)과 MIN_GAP 이상 떨어진 무작위 시각."""
    t = after.astimezone(KST)
    floor = max(t, prev + MIN_GAP) if prev else t
    for day in range(0, 5):
        c = random_time((t + dt.timedelta(days=day)).date(), floor)
        if c:
            return c
    raise RuntimeError("no slot")


def move(d, post, when, why):
    post["time"] = when.isoformat(timespec="seconds")
    post["random_time"] = True
    (d / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
    suffix = d.name.split("-", 4)[4] if d.name.count("-") >= 4 else d.name
    new = POSTS / f"{when:%Y-%m-%d-%H%M}-{suffix}"
    if not new.exists():
        d.rename(new)
    print(why, d.name, "->", new.name, post["time"])


def pending_posts():
    pending = []
    for d in sorted(POSTS.iterdir()):
        pj = d / "post.json"
        if pj.exists() and not (d / "posted.json").exists():
            pending.append((d, json.loads(pj.read_text(encoding="utf-8"))))
    pending.sort(key=lambda x: x[1]["time"])
    return pending


def reschedule_stale(now):
    """오래 밀린 게시물을 몰아 올리지 않도록 예약된 마지막 게시물 다음 날 무작위 시각으로 옮긴다."""
    pending = pending_posts()
    if not pending:
        return
    last = max(dt.datetime.fromisoformat(p["time"]) for _, p in pending)
    for d, post in pending:
        t = dt.datetime.fromisoformat(post["time"])
        if now - t <= STALE:
            continue
        base = max(last, now).astimezone(KST)
        last = next_slot((base + dt.timedelta(days=1)).replace(hour=0, minute=0), prev=last)
        move(d, post, last, "rescheduled")


def one_per_day(now):
    """남은 게시물을 하루 1개, 날마다 다른 무작위 시각으로 맞춘다. 주간 작업이 정해진 시각으로 만들어도 여기서 섞인다."""
    prev = None
    posted = [dt.datetime.fromisoformat(json.loads(p.read_text(encoding="utf-8"))["posted_at"])
              for p in POSTS.glob("*/posted.json")]
    if posted:
        prev = max(posted)
    for d, post in pending_posts():
        t = dt.datetime.fromisoformat(post["time"])
        # 이미 시간이 지난 게시물은 폴더를 옮기지 않는다 (옮기면 이번 실행의 이미지 주소가 아직 GitHub에 없다)
        if t <= now:
            prev = t
            continue
        tk = t.astimezone(KST)
        ok = (post.get("random_time") and (not prev or (t - prev >= MIN_GAP and tk.date() > prev.astimezone(KST).date())))
        if ok:
            prev = t
            continue
        day = tk.date()
        if prev and day <= prev.astimezone(KST).date():
            day = prev.astimezone(KST).date() + dt.timedelta(days=1)
        start = dt.datetime(day.year, day.month, day.day, tzinfo=KST)
        want = next_slot(max(start, now + dt.timedelta(minutes=30)), prev=prev)
        move(d, post, want, "shuffled")
        prev = want


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
BLOCK_PAUSE = dt.timedelta(hours=72)


def blocked(e):
    s = str(e)
    return "2207051" in s or "action is blocked" in s


def main():
    if not TOKEN:
        print("IG_TOKEN secret is missing - skipping until it is added")
        return
    now = dt.datetime.now(dt.timezone.utc)
    # Instagram이 활동을 제한하면(action is blocked) 계속 시도할수록 길어지므로 72시간 쉰다
    if COOLDOWN.exists():
        until = dt.datetime.fromisoformat(json.loads(COOLDOWN.read_text(encoding="utf-8"))["until"])
        if now < until:
            print(f"cooling down after Instagram action block until {until.isoformat()}")
            return
    reschedule_stale(now)
    one_per_day(now)
    # 하루 1개만 올라가도록 최근 게시 후 15시간은 쉰다 (예약 간격은 16시간 이상)
    last = [dt.datetime.fromisoformat(json.loads(p.read_text(encoding="utf-8"))["posted_at"])
            for p in POSTS.glob("*/posted.json")]
    if last and now - max(last) < dt.timedelta(hours=15):
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
                print(f"::error::Instagram이 활동을 제한했어요. 72시간 쉬고 다시 시도해요: {e}")
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
