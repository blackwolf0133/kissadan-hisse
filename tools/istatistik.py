"""Hesap ve Reels istatistiklerini resmi Meta API'den okur, JSON olarak yazar.
Hiçbir şey paylaşmaz. Insights izni yoksa o kısmı atlar."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import publisher as p  # noqa: E402

token = os.environ["IG_ACCESS_TOKEN"]
mode = p.detect_mode(token)
base = f"https://{p._host(mode)}/{p.API_VERSION}"
uid = p.resolve_user_id(token, mode)


def get(path, **params):
    try:
        return p._request("GET", f"{base}/{path}", dict(params, access_token=token))
    except p.PublishError as e:
        return {"hata": str(e)[:400]}


out = {"hesap": get(uid, fields="username,name,biography,website,followers_count,follows_count,media_count")}
out["hesap_insights"] = get(f"{uid}/insights", metric="reach,views,total_interactions",
                            period="day", metric_type="total_value")

medya = get(f"{uid}/media", limit=50,
            fields="id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count")
out["medya"] = []
for m in medya.get("data", []):
    m["caption"] = (m.get("caption") or "")[:120]
    ins = get(f"{m['id']}/insights",
              metric="reach,views,likes,comments,shares,saved,total_interactions,"
                     "ig_reels_avg_watch_time,ig_reels_video_view_total_time")
    if "data" in ins:
        m["insights"] = {d["name"]: (d.get("values") or [{}])[0].get("value") for d in ins["data"]}
    else:
        m["insights_hata"] = ins.get("hata", "")[:200]
    out["medya"].append(m)
if "hata" in medya:
    out["medya_hata"] = medya["hata"]

print("=====ISTATISTIK_BASLA=====")
print(json.dumps(out, ensure_ascii=False, indent=1))
print("=====ISTATISTIK_BITTI=====")
