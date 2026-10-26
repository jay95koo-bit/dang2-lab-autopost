"""posts/<slot>/post.json 을 읽어 카드뉴스 이미지(1.jpg, 2.jpg ...)를 만든다.

이미 이미지가 있는 게시물은 건너뛴다. 사진은 Pexels CDN에서 받는다.
사용: python render.py            (모든 게시물)
      python render.py --local DIR (사진을 DIR/<pexels_id>.jpg 에서 읽음, 테스트용)
"""
import html
import re
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
POSTS = pathlib.Path(os.environ.get("POSTS_DIR", ROOT / "posts"))
HANDLE = "dang2_lab"
INK = "#1F1A16"
CREAM = "#FFF7EC"
ACCENT = "#FF7A2F"
HILITE = "#FFD84D"
W, H = 1080, 1350

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;overflow:hidden;background:{CREAM};color:{INK};
  font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;word-break:keep-all}}
.photo{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover}}
mark{{background:linear-gradient(180deg,transparent 64%,{HILITE} 64%,{HILITE} 100%);color:inherit;padding:0 4px}}
.dark mark{{background:none;color:{HILITE}}}
.handle{{position:absolute;font-size:30px;font-weight:900;letter-spacing:-.5px}}
.page{{position:absolute;top:56px;right:64px;font-size:28px;font-weight:700;opacity:.55}}
/* cover */
.shade{{position:absolute;left:0;right:0;bottom:0;height:900px;
  background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.55) 35%,rgba(0,0,0,.88) 100%)}}
.cover{{position:absolute;left:80px;right:80px;bottom:150px;color:#fff;display:flex;flex-direction:column;gap:30px}}
.kicker{{align-self:flex-start;background:{ACCENT};color:#fff;font-size:34px;font-weight:900;padding:12px 26px;border-radius:14px;letter-spacing:-.5px}}
h1{{font-size:108px;font-weight:900;line-height:1.16;letter-spacing:-4px;white-space:pre-line}}
.sub{{font-size:38px;font-weight:500;opacity:.9;letter-spacing:-.5px}}
.swipe{{position:absolute;right:80px;bottom:70px;color:#fff;font-size:30px;font-weight:700;opacity:.85}}
/* point */
.pic{{position:absolute;top:0;left:0;width:{W}px;height:610px;object-fit:cover}}
.txt{{position:absolute;top:610px;left:0;right:0;bottom:0;padding:58px 80px 0;display:flex;flex-direction:column;gap:22px}}
.lab{{font-size:32px;font-weight:900;color:{ACCENT};letter-spacing:-.5px}}
.big{{font-size:104px;font-weight:900;letter-spacing:-4px;line-height:1.05}}
h2{{font-size:56px;font-weight:900;letter-spacing:-2px;line-height:1.28;white-space:pre-line}}
p{{font-size:40px;font-weight:500;line-height:1.62;letter-spacing:-.8px;color:#3d342d}}
.txt .handle{{position:static;margin-top:auto;padding-bottom:56px;font-size:28px;color:{ACCENT}}}
.alert{{background:#2A211B;color:#fff}}
.alert .txt{{top:0;padding-top:140px}}
.alert .lab{{color:#FF6B5B;font-size:40px}}
.alert h2{{font-size:76px}}
.alert p{{color:rgba(255,255,255,.88);font-size:42px}}
/* check */
.check{{position:absolute;inset:0;padding:120px 80px 0;display:flex;flex-direction:column;gap:20px}}
.check h2{{font-size:66px;margin-bottom:26px}}
.row{{display:flex;gap:26px;align-items:flex-start;background:#fff;border-radius:22px;padding:30px 34px;box-shadow:0 2px 0 rgba(0,0,0,.06)}}
.box{{width:46px;height:46px;border:5px solid {ACCENT};border-radius:10px;flex-shrink:0;margin-top:4px}}
.row span{{font-size:40px;font-weight:700;letter-spacing:-1px;line-height:1.4}}
.save{{margin-top:28px;font-size:34px;font-weight:700;color:{ACCENT};text-align:center}}
.check~.handle{{left:0;right:0;bottom:60px;text-align:center;color:#a8988a}}
"""


def esc(s):
    """==강조== 는 형광펜 표시로 바꾼다."""
    return re.sub(r"==(.+?)==", r"<mark>\1</mark>", html.escape(s or ""))


def slide_html(s, photo_src, i, n):
    t = s.get("type", "point")
    page = f'<div class="page">{i}/{n}</div>'
    cls = ""
    if t == "cover":
        cls = "dark"
        sub = f'<div class="sub">{esc(s["sub"])}</div>' if s.get("sub") else ""
        kicker = f'<div class="kicker">{esc(s["kicker"])}</div>' if s.get("kicker") else ""
        body = (f'<img class="photo" src="{photo_src}"><div class="shade"></div>'
                f'<div class="cover">{kicker}<h1>{esc(s["title"])}</h1>{sub}</div>'
                f'<div class="handle" style="left:80px;bottom:70px;color:#fff;opacity:.85">@{HANDLE}</div>'
                f'<div class="swipe">넘겨 보기 →</div>')
    elif t == "check":
        rows = "".join(f'<div class="row"><div class="box"></div><span>{esc(x)}</span></div>' for x in s["items"])
        save = f'<div class="save">{esc(s.get("save", "저장해 두고 하나씩 체크해 보세요"))}</div>'
        body = (f'{page}<div class="check"><h2>{esc(s["h"])}</h2>{rows}{save}</div>'
                f'<div class="handle">@{HANDLE}</div>')
    else:
        alert = t == "alert"
        cls = "alert" if alert else ""
        lab = f'<div class="lab">{esc(s["lab"])}</div>' if s.get("lab") else ""
        big = f'<div class="big">{esc(s["big"])}</div>' if s.get("big") else ""
        pic = "" if alert or not photo_src else f'<img class="pic" src="{photo_src}">'
        body = (f'{pic}{page if alert else ""}<div class="txt">{lab}{big}<h2>{esc(s["h"])}</h2>'
                f'<p>{esc(s.get("p"))}</p><div class="handle">@{HANDLE}</div></div>')
    return (f'<html><head><meta charset="utf-8"><style>{CSS}</style></head>'
            f'<body class="{cls}">{body}</body></html>')


def pexels_url(pid):
    return (f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg"
            f"?auto=compress&cs=tinysrgb&w={W}&h={H}&fit=crop")


def fetch_photo(pid, cache, local_dir=None):
    dest = cache / f"{pid}.jpg"
    if dest.exists():
        return dest
    if local_dir:
        return pathlib.Path(local_dir) / f"{pid}.jpg"
    req = urllib.request.Request(pexels_url(pid), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def used_ids():
    ids = set()
    for pj in POSTS.glob("*/post.json"):
        for s in json.loads(pj.read_text(encoding="utf-8"))["slides"]:
            if isinstance(s.get("photo"), int):
                ids.add(s["photo"])
    return ids


def resolve_query(q, used):
    """photo 에 숫자 대신 검색어가 들어 있으면 Pexels API로 세로 사진을 찾는다 (PEXELS_KEY 필요)."""
    import os
    key = os.environ.get("PEXELS_KEY")
    if not key:
        raise SystemExit(f"photo query '{q}' needs PEXELS_KEY secret")
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": q, "orientation": "portrait", "per_page": 20})
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        photos = json.loads(r.read())["photos"]
    for p in photos:
        if p["id"] not in used:
            used.add(p["id"])
            return p["id"]
    raise SystemExit(f"no photo for '{q}'")


def main():
    local_dir = sys.argv[sys.argv.index("--local") + 1] if "--local" in sys.argv else None
    from playwright.sync_api import sync_playwright

    cache = ROOT / ".photo_cache"
    cache.mkdir(exist_ok=True)
    todo = [d for d in sorted(POSTS.iterdir()) if (d / "post.json").exists() and not (d / "1.jpg").exists()]
    if not todo:
        print("nothing to render")
        return
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H})
        used = used_ids()
        for d in todo:
            post = json.loads((d / "post.json").read_text(encoding="utf-8"))
            changed = False
            for s in post["slides"]:
                if isinstance(s.get("photo"), str):
                    s["photo_query"] = s["photo"]
                    s["photo"] = resolve_query(s["photo"], used)
                    changed = True
            if changed:
                (d / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
            n = len(post["slides"])
            for i, s in enumerate(post["slides"], 1):
                uri = fetch_photo(s["photo"], cache, local_dir).resolve().as_uri() if s.get("photo") else ""
                tmp = d / f"_slide{i}.html"
                tmp.write_text(slide_html(s, uri, i, n), encoding="utf-8")
                page.goto(tmp.resolve().as_uri())
                page.wait_for_timeout(400)
                page.screenshot(path=str(d / f"{i}.jpg"), type="jpeg", quality=92)
                tmp.unlink()
            print("rendered", d.name, len(post["slides"]), "slides")
        browser.close()


if __name__ == "__main__":
    main()
