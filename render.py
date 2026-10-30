"""posts/<slot>/post.json 을 읽어 카드뉴스 이미지(1.jpg, 2.jpg ...)를 만든다.

이미 이미지가 있는 게시물은 건너뛴다. 사진은 Pexels CDN에서 받는다.
사용: python render.py            (모든 게시물)
      python render.py --local DIR (사진을 DIR/<pexels_id>.jpg 에서 읽음, 테스트용)
"""
import html
import json
import pathlib
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
POSTS = ROOT / "posts"
HANDLE = "dang2_lab"
ACCENT = "#FFB547"
W, H = 1080, 1350

CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;overflow:hidden;background:#2B2622;
  font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;color:#fff}}
.photo{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover}}
.shade{{position:absolute;left:0;right:0;bottom:0;
  background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.6) 38%,rgba(0,0,0,.9) 100%)}}
.handle-top{{position:absolute;top:56px;right:64px;font-size:40px;font-weight:900;letter-spacing:-1px;color:{ACCENT}}}
.handle-bottom{{position:absolute;left:0;right:0;bottom:84px;text-align:center;font-size:42px;font-weight:900;letter-spacing:-1px;color:{ACCENT}}}
.cover{{position:absolute;left:88px;right:88px;bottom:230px;display:flex;flex-direction:column;gap:28px}}
.badge{{align-self:flex-start;background:{ACCENT};color:#1E1A17;font-size:30px;font-weight:700;padding:10px 22px;border-radius:999px}}
h1{{font-size:100px;font-weight:900;line-height:1.2;letter-spacing:-3px;white-space:pre-line}}
.body{{position:absolute;left:88px;right:88px;bottom:100px;display:flex;flex-direction:column;gap:26px}}
.hrow{{display:flex;align-items:center;gap:20px}}
.num{{width:60px;height:60px;border-radius:50%;background:{ACCENT};color:#1E1A17;font-size:34px;font-weight:900;
  display:flex;align-items:center;justify-content:center;flex-shrink:0}}
h2{{font-size:58px;font-weight:700;letter-spacing:-1.5px;line-height:1.3}}
p{{font-size:37px;font-weight:500;line-height:1.75;color:rgba(255,255,255,.94)}}
.box{{background:rgba(255,255,255,.1);border-radius:20px;padding:28px 32px;font-size:40px;font-weight:700;text-align:center;color:{ACCENT}}}
.table{{display:grid;grid-template-columns:1fr 1fr;border-top:2px solid rgba(255,255,255,.25)}}
.table div{{padding:22px 8px;font-size:38px;border-bottom:2px solid rgba(255,255,255,.15)}}
.table .v{{text-align:right;font-weight:700;color:{ACCENT}}}
/* places: 장소 총정리 (밝은 배경, 사진 없음) */
body.light{{background:#F5F1EA;color:#1F1A16}}
.pl{{position:absolute;inset:0;padding:64px 72px 0;display:flex;flex-direction:column;gap:18px}}
.pl .tag{{align-self:flex-start;background:#1F1A16;color:#fff;font-size:30px;font-weight:700;padding:10px 22px;border-radius:12px}}
.pl h2{{font-size:58px;font-weight:900;letter-spacing:-2px;line-height:1.2;margin-bottom:10px}}
.card{{background:#fff;border-radius:26px;padding:22px 32px;display:flex;flex-direction:column;gap:10px;box-shadow:0 3px 0 rgba(0,0,0,.05)}}
.nm{{display:flex;align-items:center;gap:16px;flex-wrap:wrap}}
.nm b{{font-size:44px;font-weight:900;letter-spacing:-1.5px}}
.nm i{{font-style:normal;font-size:26px;font-weight:700;color:#6B5E52;background:#EFE8DD;padding:6px 14px;border-radius:10px}}
.chips{{display:flex;gap:10px;flex-wrap:wrap}}
.chips span{{font-size:27px;font-weight:700;background:#E6F5C9;color:#2F4A0E;padding:6px 16px;border-radius:10px;letter-spacing:-.5px}}
.ft{{font-size:28px;font-weight:500;color:#5A4E44;letter-spacing:-.5px;line-height:1.45}}
.note{{position:absolute;left:72px;right:72px;bottom:44px;display:flex;justify-content:space-between;font-size:25px;color:#8A7C70}}
.note b{{color:{ACCENT};font-weight:900;font-size:30px;filter:brightness(.85)}}
"""


def esc(s):
    return html.escape(s or "")


def slide_html(s, photo_src):
    t = s.get("type", "body")
    if t == "places":
        cards = "".join(
            f'<div class="card"><div class="nm"><b>{esc(x["name"])}</b><i>{esc(x["area"])}</i></div>'
            f'<div class="chips">{"".join(f"<span>{esc(c)}</span>" for c in x.get("chips", []))}</div>'
            f'<div class="ft">{esc(x.get("desc"))}</div></div>' for x in s["items"])
        tag = f'<div class="tag">{esc(s["tag"])}</div>' if s.get("tag") else ""
        return (f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body class="light">'
                f'<div class="pl">{tag}<h2>{esc(s["h"])}</h2>{cards}</div>'
                f'<div class="note"><span>{esc(s.get("note", "2026년 10월 기준 · 방문 전 매장에 꼭 확인해 주세요"))}</span><b>{HANDLE}</b></div>'
                f'</body></html>')
    parts = [f'<img class="photo" src="{photo_src}">']
    if t == "cover":
        parts.append('<div class="shade" style="height:820px"></div>')
        badge = f'<div class="badge">{esc(s.get("badge"))}</div>' if s.get("badge") else ""
        parts.append(f'<div class="cover">{badge}<h1>{esc(s["title"])}</h1></div>')
        parts.append(f'<div class="handle-bottom">{HANDLE}</div>')
    else:
        shade = {"table": 1000, "formula": 860}.get(t, 760)
        parts.append(f'<div class="shade" style="height:{shade}px"></div>')
        parts.append(f'<div class="handle-top">{HANDLE}</div>')
        head = f'<h2>{esc(s["h"])}</h2>'
        if s.get("n"):
            head = f'<div class="hrow"><span class="num">{esc(s["n"])}</span>{head}</div>'
        inner = head
        if t == "table":
            rows = "".join(f'<div>{esc(a)}</div><div class="v">{esc(b)}</div>' for a, b in s["rows"])
            inner += f'<div class="table">{rows}</div>'
        else:
            if s.get("p"):
                inner += f'<p>{esc(s["p"])}</p>'
            if s.get("box"):
                inner += f'<div class="box">{esc(s["box"])}</div>'
            if s.get("p2"):
                inner += f'<p>{esc(s["p2"])}</p>'
        parts.append(f'<div class="body">{inner}</div>')
    return f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'


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


def render_post(d, page, cache, used, local_dir):
    post = json.loads((d / "post.json").read_text(encoding="utf-8"))
    changed = False
    for s in post["slides"]:
        if isinstance(s.get("photo"), str) and s["photo"]:
            s["photo_query"] = s["photo"]
            s["photo"] = resolve_query(s["photo"], used)
            changed = True
    if changed:
        (d / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
    for i, s in enumerate(post["slides"], 1):
        photo = fetch_photo(s["photo"], cache, local_dir).resolve().as_uri() if s.get("photo") else ""
        tmp = d / f"_slide{i}.html"
        tmp.write_text(slide_html(s, photo), encoding="utf-8")
        page.goto(tmp.resolve().as_uri())
        page.wait_for_timeout(300)
        page.screenshot(path=str(d / f"{i}.jpg"), type="jpeg", quality=92)
        tmp.unlink()
    print("rendered", d.name, len(post["slides"]), "slides")


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
        failed = []
        for d in todo:
            try:
                render_post(d, page, cache, used, local_dir)
            except Exception as e:  # 한 게시물이 실패해도 나머지는 계속 만든다
                failed.append(d.name)
                for f in d.glob("*.jpg"):
                    f.unlink()
                print(f"::warning::{d.name} 렌더 실패: {e}")
        browser.close()


if __name__ == "__main__":
    main()
