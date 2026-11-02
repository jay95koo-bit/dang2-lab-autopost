import urllib.request, io, collections
from PIL import Image, ImageDraw, ImageFont
TW, TH = 240, 300
font = ImageFont.load_default(size=20)
rows = collections.OrderedDict()
for line in open("preview/cands.txt"):
    k, *ids = line.split()
    rows.setdefault(k.split("-")[0], []).append((k, ids))
cache = {}
def get(pid):
    if pid in cache: return cache[pid]
    url = f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg?auto=compress&cs=tinysrgb&w={TW}&h={TH}&fit=crop"
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60)
        im = Image.open(io.BytesIO(r.read())).convert("RGB").resize((TW, TH))
    except Exception as e:
        im = Image.new("RGB", (TW, TH), (200, 0, 0)); print("FAIL", pid, e)
    cache[pid] = im; return im
for post, lines in rows.items():
    sheet = Image.new("RGB", (60 + 4 * (TW + 10), len(lines) * (TH + 40)), "white")
    d = ImageDraw.Draw(sheet)
    for r, (k, ids) in enumerate(lines):
        y = r * (TH + 40)
        d.text((5, y + 10), k.split("-")[1], fill="black", font=font)
        for c, pid in enumerate(ids):
            x = 60 + c * (TW + 10)
            sheet.paste(get(pid), (x, y))
            d.text((x, y + TH + 5), pid, fill="black", font=font)
    sheet.save(f"preview/{post}.jpg", quality=80)
