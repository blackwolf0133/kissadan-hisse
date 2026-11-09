"""Kıssadan Hisse (@kissadan.hisse.tr) - günlük otomasyon (her akşam 21:30).

Akış: 'Hazırla' iş akışı sıradaki bölümü önceden üretir (hazir-<id> sürümüne koyar),
'Günlük paylaşım' iş akışı hazır olan ilk bölümü Instagram'a yükler.

Komutlar:
  python daily.py status
  python daily.py pick-prepare  (READY="hazır id'ler")   -> hazırlanacak bölüm
  python daily.py pick-publish  (READY="hazır id'ler")   -> paylaşılacak bölüm
  python daily.py caption <id>                           -> paylaşım metni
  python daily.py publish <id> --video-url U             -> paylaşır ve kaydeder
  python daily.py check | refresh-token
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state", "posted.json")
AI_NOTE = "Görseller ve ses yapay zekâ ile üretildi. Kıssa, halk anlatılarından kendi sözlerimizle uyarlandı."


def today_tr():
    return (dt.datetime.utcnow() + dt.timedelta(hours=3)).date().isoformat()


def set_output(key, val):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"{key}={val}\n")
    print(f"{key}={val}")


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"posted": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def queue():
    done = {p["id"] for p in load_state()["posted"]}
    eps = []
    for path in sorted(glob.glob(os.path.join(ROOT, "episodes", "[0-9]*.json"))):
        ep = json.load(open(path, encoding="utf-8"))
        if ep["id"] not in done and not ep.get("skip"):
            eps.append((os.path.relpath(path, ROOT), ep))
    return eps


def find(eid):
    for path in glob.glob(os.path.join(ROOT, "episodes", f"{eid}_*.json")):
        return path, json.load(open(path, encoding="utf-8"))
    sys.exit(f"bölüm yok: {eid}")


def ready_ids():
    return set(os.environ.get("READY", "").split())


def cmd_status(_):
    q = queue()
    print(f"Sırada {len(q)} bölüm var.")
    for path, ep in q[:10]:
        print(f"  {ep['id']}  {ep['title']}")
    if len(q) < 5:
        print("::warning::Sırada 5'ten az bölüm kaldı - yeni senaryolar eklenmeli!")


def cmd_pick_prepare(_):
    forced = os.environ.get("FORCE_ID", "").split()
    if forced:
        path, ep = find(forced[0])
        set_output("id", ep["id"])
        set_output("path", os.path.relpath(path, ROOT))
        set_output("rest", " ".join(forced[1:]))
        return
    ready = ready_ids()
    ahead = int(os.environ.get("AHEAD", "3"))
    q = queue()
    if sum(1 for _, ep in q if ep["id"] in ready) >= ahead:
        print(f"Önceden hazır {ahead} bölüm var, yeni üretim gerekmiyor.")
        set_output("id", "")
        return
    for path, ep in q:
        if ep["id"] not in ready:
            set_output("id", ep["id"])
            set_output("path", path)
            return
    print("::warning::Hazırlanacak bölüm kalmadı!")
    set_output("id", "")


def cmd_pick_publish(_):
    hour_tr = (dt.datetime.utcnow() + dt.timedelta(hours=3)).hour
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and not (20 <= hour_tr < 24):
        print(f"Zamanlayıcı geç tetiklendi (TR saat {hour_tr}), gece paylaşımı yapılmıyor.")
        set_output("id", "")
        return
    if os.environ.get("FORCE") != "1" and not os.path.exists(os.path.join(ROOT, "assets", "yayinda")):
        print("Kanal henüz yayında değil (assets/yayinda yok).")
        set_output("id", "")
        return
    if os.environ.get("FORCE") != "1" and any(p.get("date") == today_tr() for p in load_state()["posted"]):
        print(f"Bugün ({today_tr()}) zaten paylaşım yapıldı.")
        set_output("id", "")
        return
    ready = ready_ids()
    q = queue()
    if not q:
        print("::error::Sırada bölüm yok!")
        sys.exit(1)
    eid = q[0][1]["id"]
    if eid not in ready:
        print(f"::error::Sıradaki bölüm ({eid}) henüz hazır değil.")
        set_output("id", "")
        sys.exit(1)
    set_output("id", eid)


def caption(ep):
    return f"{ep['caption']}\n\n{AI_NOTE}\n\n{' '.join(ep.get('hashtags', [])[:5])}"


def cmd_caption(a):
    print(caption(find(a.id)[1]))



def paylas_tekrarli(publisher, video_path, video_url, caption, deneme=3):
    """Meta videoyu arada bir işleyemiyor (ProcessingFailedError). Hata yayınlamadan ÖNCEKİ aşamadaysa
    1-2 dk bekleyip YENİ bir yükleme kaydıyla tekrar dener; 2. denemede videoyu doğrudan yükler.
    media_publish aşamasındaki hatalar tekrar denenmez (çift paylaşım olmasın)."""
    import time
    for n in range(deneme):
        url = video_url if (n != 1 or not video_path) else None
        try:
            return publisher.publish_reel(video_path=video_path, video_url=url, caption=caption)
        except publisher.PublishError as e:
            if "media_publish" in str(e) or n == deneme - 1:
                raise
            bekle = 60 * (n + 1)
            print(f"::warning::Paylaşım denemesi {n + 1} olmadı, {bekle} sn sonra yeni kayıtla tekrar: {str(e)[:200]}",
                  flush=True)
            time.sleep(bekle)


def cmd_publish(a):
    import publisher
    _, ep = find(a.id)
    res = paylas_tekrarli(publisher, a.video_path, a.video_url, caption(ep))
    st = load_state()
    st["posted"].append({"id": ep["id"], "title": ep["title"], "date": today_tr(),
                         "media_id": res["media_id"], "permalink": res.get("permalink")})
    save_state(st)
    print(f"Paylaşıldı: {ep['title']} -> {res.get('permalink')}")


def cmd_check(_):
    import publisher
    me, lim = publisher.check_account()
    print("Hesap:", me.get("username"), "| Paylaşım kotası:", lim)


def cmd_refresh(_):
    import publisher
    if os.environ.get("IG_ACCESS_TOKEN", "").startswith("EAA"):
        print("Bu anahtar türü süresiz, yenileme gerekmez.")
        return
    tok, exp = publisher.refresh_token()
    if not tok:
        print("::error::Token yenilenemedi")
        sys.exit(1)
    print(f"Token yenilendi, {(exp or 0) // 86400} gün geçerli.")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        print(f"::add-mask::{tok}")
        with open(out, "a") as fh:
            fh.write(f"token={tok}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("pick-prepare")
    sub.add_parser("pick-publish")
    p = sub.add_parser("caption"); p.add_argument("id")
    p = sub.add_parser("publish"); p.add_argument("id"); p.add_argument("--video-url"); p.add_argument("--video-path")
    sub.add_parser("check")
    sub.add_parser("refresh-token")
    a = ap.parse_args()
    {"status": cmd_status, "pick-prepare": cmd_pick_prepare, "pick-publish": cmd_pick_publish,
     "caption": cmd_caption, "publish": cmd_publish, "check": cmd_check, "refresh-token": cmd_refresh}[a.cmd](a)
