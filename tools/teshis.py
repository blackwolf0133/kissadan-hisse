"""Anahtarın neye erişebildiğini gösterir (anahtarın kendisini yazmaz)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import publisher as P
t = os.environ["IG_ACCESS_TOKEN"]
g = f"https://graph.facebook.com/{P.API_VERSION}"
def dene(ad, url, prm):
    try:
        r = P._request("GET", url, dict(prm, access_token=t))
        print(f"{ad}: {json.dumps(r, ensure_ascii=False)[:1500]}")
        return r
    except Exception as e:  # noqa: BLE001
        print(f"{ad}: HATA {str(e)[:300]}")
d = dene("debug_token", f"{g}/debug_token", {"input_token": t})
dene("me", f"{g}/me", {"fields": "id,name"})
dene("me/accounts", f"{g}/me/accounts", {"fields": "name,instagram_business_account{id,username}"})
ids = set()
for s in ((d or {}).get("data", {}).get("granular_scopes") or []):
    ids.update(s.get("target_ids") or [])
for i in sorted(ids):
    dene(f"hedef {i}", f"{g}/{i}", {"fields": "id,username,name"})

