"""Paylaşım saat kapısı (14 Kasım). Sadece standart kütüphane.

GitHub'ın zamanlayıcısı bu depolarda saatlerce gecikiyor ya da hiç çalışmıyor; Claude yedek alarmları da
kullanım limitine takılabiliyor. Bu yüzden iş akışı her 15 dakikada bir kısa bir kontrol yapar:
  * SLOTLAR (TR saati, ör. "06:50,11:20,17:20") içinde şu andan önceki EN SON vakit seçilir,
  * o vakitte henüz paylaşım yapılmadıysa ve sonraki vakte (sonuncusu için 23:30'a) gelinmediyse paylaşılır.
Kaçırılan bir vakit telafi edilmez (aynı anda iki video atılmasın diye), sıradaki vakitte devam edilir.
Kayıtlarda "slot" alanı vardır; eski kayıtlar (slot yok) günün SON vaktini karşılamış sayılır.

Kullanım:  python3 saat_kapisi.py   -> GITHUB_OUTPUT'a git=1/0 ve slot=HH:MM yazar
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SON_SINIR = "23:30"
GEC_KALMA_DK = 180  # bir vakit en fazla 3 saat geç telafi edilir


def simdi_tr():
    return dt.datetime.utcnow() + dt.timedelta(hours=3)


def slotlar():
    s = os.environ.get("SLOTLAR", "").strip()
    if not s:
        p = os.path.join(ROOT, "kanal", "slotlar.txt")
        if os.path.exists(p):
            s = open(p, encoding="utf-8").read().strip()
    return sorted(x.strip() for x in s.replace("\n", ",").split(",") if x.strip())


def _dk(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def gecerli_slot(now=None):
    """(slot, sonraki_sinir) ya da (None, None)."""
    now = now or simdi_tr()
    dk = now.hour * 60 + now.minute
    sl = slotlar()
    gecmis = [s for s in sl if _dk(s) <= dk]
    if not gecmis:
        return None, None
    cur = gecmis[-1]
    i = sl.index(cur)
    sinir = sl[i + 1] if i + 1 < len(sl) else SON_SINIR
    if _dk(sinir) > _dk(cur) + GEC_KALMA_DK:
        sinir = "%02d:%02d" % divmod(_dk(cur) + GEC_KALMA_DK, 60)
    if dk >= _dk(sinir):
        return None, None
    return cur, sinir


def kayitlar():
    p = os.path.join(ROOT, "state", "posted.json")
    if not os.path.exists(p):
        return []
    d = json.load(open(p, encoding="utf-8"))
    return d.get("posted", []) if isinstance(d, dict) else d


def slot_dolu(slot, now=None):
    now = now or simdi_tr()
    bugun = now.date().isoformat()
    sl = slotlar()
    for p in kayitlar():
        if p.get("date") != bugun:
            continue
        ps = p.get("slot")
        if ps == slot or (not ps and sl and slot == sl[-1]):
            return True
    return False


def karar(now=None):
    """(git: bool, slot: str, neden: str)"""
    now = now or simdi_tr()
    if os.environ.get("FORCE") == "1":
        return True, gecerli_slot(now)[0] or "elle", "zorla"
    slot, sinir = gecerli_slot(now)
    if not slot:
        return False, "", f"Şu an ({now:%H:%M}) paylaşım vakti değil. Vakitler: {', '.join(slotlar())}"
    if slot_dolu(slot, now):
        return False, slot, f"{slot} vaktinin paylaşımı zaten yapıldı."
    return True, slot, f"{slot} vakti: paylaşım yapılacak (en geç {sinir})."


def _out(k, v):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        with open(p, "a") as f:
            f.write(f"{k}={v}\n")


if __name__ == "__main__":
    git, slot, neden = karar()
    print(neden)
    _out("git", "1" if git else "0")
    _out("slot", slot)
    sys.exit(0)
