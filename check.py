"""연결 확인용: 게시하지 않고 계정 정보와 게시 한도만 조회한다."""
import json, os, urllib.request, urllib.parse
T = os.environ.get("IG_TOKEN", "")
if not T:
    raise SystemExit("IG_TOKEN 없음")
def get(path, **p):
    p["access_token"] = T
    try:
        with urllib.request.urlopen("https://graph.instagram.com/" + path + "?" + urllib.parse.urlencode(p), timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit("API error %s: %s" % (e.code, e.read().decode(errors="replace").replace(T, "***")))
me = get("me", fields="user_id,username,account_type")
print("account:", me.get("username"), me.get("account_type"))
lim = get(f"{me['user_id']}/content_publishing_limit", fields="quota_usage,config")
print("publish limit:", json.dumps(lim))
