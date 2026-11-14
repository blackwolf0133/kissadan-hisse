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
import saat_kapisi
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state", "posted.json")
AI_NOTE = "Görseller ve ses yapay zekâ ile üretildi. Kıssa, halk anlatılarından kendi sözlerimizle uyarlandı."


import time as _t
_SURECIN_BASI = _t.time()

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
    if os.environ.get("FORCE") != "1" and not os.path.exists(os.path.join(ROOT, "assets", "yayinda")):
        print("Kanal henüz yayında değil (assets/yayinda yok).")
        set_output("id", "")
        return
    _git, _slot, _neden = saat_kapisi.karar()
    if not _git:
        print(_neden)
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



def guvenli_kodla(video_path):
    """14 Kasım: Meta bazen 'Video Transcoding Error' / 2207082 verip videoyu hiç işleyemiyor.
    Videoyu Instagram'ın en sorunsuz kabul ettiği biçime yeniden kodlar (H.264 Main, sabit 30 fps,
    AAC 48 kHz stereo, faststart). ffmpeg yoksa ya da hata olursa None döner."""
    import shutil, subprocess
    if not video_path or not os.path.exists(video_path) or not shutil.which("ffmpeg"):
        return None
    out = os.path.splitext(video_path)[0] + "_guvenli.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_path,
           "-c:v", "libx264", "-profile:v", "main", "-level", "4.1", "-pix_fmt", "yuv420p",
           "-preset", "veryfast", "-b:v", "3500k", "-maxrate", "4500k", "-bufsize", "9000k",
           "-r", "30", "-g", "60", "-bf", "0", "-vf", "scale=1080:1920:flags=lanczos,setsar=1",
           "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", out]
    try:
        subprocess.run(cmd, check=True, timeout=600)
        print(f"Video güvenli biçimde yeniden kodlandı: {out}", flush=True)
        return out
    except Exception as e:
        print(f"::warning::Yeniden kodlama olmadı: {e}", flush=True)
        return None


def paylas_tekrarli(publisher, video_path, video_url, caption, deneme=4):
    """Meta videoyu arada bir işleyemiyor (ProcessingFailedError / Transcoding Error / 2207082).
    Hata yayınlamadan ÖNCEKİ aşamadaysa yeni bir yükleme kaydıyla tekrar dener:
    1. deneme: adresten, 2. deneme: dosyadan, 3-4. deneme: yeniden kodlanmış dosyadan.
    media_publish aşamasındaki hatalar tekrar denenmez (çift paylaşım olmasın)."""
    import time
    guvenli = None
    for n in range(deneme):
        path, url = video_path, video_url
        if n == 1 and video_path:
            url = None
        elif n >= 2:
            if guvenli is None:
                guvenli = guvenli_kodla(video_path) or ""
            if guvenli:
                path, url = guvenli, None
        try:
            return publisher.publish_reel(video_path=path, video_url=url, caption=caption)
        except publisher.PublishError as e:
            if "media_publish" in str(e) or n == deneme - 1:
                raise
            bekle = 60 * min(n + 1, 2)
            print(f"::warning::Paylaşım denemesi {n + 1} olmadı, {bekle} sn sonra yeni kayıtla tekrar: {str(e)[:200]}",
                  flush=True)
            time.sleep(bekle)

def hikaye_paylas(publisher, video_path, video_url):
    """Reel'den sonra aynı videoyu hikâyeye koyar. Hata olursa sadece uyarı verir:
    Reel zaten paylaşıldı ve kaydı yazıldı, hikâye yüzünden iş akışı ASLA başarısız olmamalı.
    14 Kasım: Instagram bazen videoyu işleyemiyor -> 3 deneme, ama süre bütçeli
    (iş zaman aşımına uğrarsa paylaşım kaydı yazılmaz ve ertesi gün aynı Reel tekrar paylaşılır!)."""
    import time
    if os.environ.get("HIKAYE_KAPALI") == "1":
        print("Hikâye paylaşımı kapalı (HIKAYE_KAPALI=1).")
        return None
    bitis = min(_SURECIN_BASI + 30 * 60, time.time() + 14 * 60)
    for deneme in range(1, 4):
        kalan = bitis - time.time()
        if kalan < 150:
            print(f"::warning::Hikâye için süre kalmadı, atlandı (deneme {deneme}).")
            return None
        try:
            r = publisher.publish_story(video_path=video_path, video_url=video_url,
                                        bekleme=int(min(420, kalan - 30)))
            print(f"Hikâye paylaşıldı: {r['media_id']} (deneme {deneme})")
            return r["media_id"]
        except Exception as e:
            print(f"::warning::Hikâye denemesi {deneme} olmadı (Reel etkilenmedi): {str(e)[:300]}")
            if deneme < 3:
                time.sleep(min(60 * deneme, max(0, bitis - time.time() - 150)))
    return None


def cmd_publish(a):
    import publisher
    _, ep = find(a.id)
    res = paylas_tekrarli(publisher, a.video_path, a.video_url, caption(ep))
    st = load_state()
    st["posted"].append({"id": ep["id"], "title": ep["title"], "date": today_tr(), "slot": saat_kapisi.gecerli_slot()[0] or "",
                         "media_id": res["media_id"], "permalink": res.get("permalink")})
    save_state(st)
    print(f"Paylaşıldı: {ep['title']} -> {res.get('permalink')}")
    hid = hikaye_paylas(publisher, a.video_path, a.video_url)
    if hid:
        st = load_state()
        st["posted"][-1]["story_id"] = hid
        save_state(st)


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
