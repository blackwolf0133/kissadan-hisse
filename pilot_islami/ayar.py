"""İslami kanal PİLOTU için Kıssadan Hisse motorunun ayarları.

engine/ altındaki hiçbir dosya değiştirilmez: bu modül içe aktarıldığında motorun stilini, başlığını,
son kartını, görsel kontrol talimatını ve fon müziğini SADECE bu süreç için değiştirir.
Kıssadan Hisse'nin günlük üretimi bundan etkilenmez (o, engine.* modüllerini doğrudan çalıştırır)."""
import os

import numpy as np
from PIL import Image, ImageDraw

try:                                   # çizim makinesinde var; birleştirme makinesinde huggingface_hub yok
    from engine import scenes as SC
except ImportError:
    SC = type("YokSC", (), {})()
from engine import ses as S
from engine import video as V

SERI = os.environ.get("PILOT_SERI", "BİR HADİS · BİR GÜN")
V.HANDLE = os.environ.get("PILOT_HANDLE", "")
V.AMBER = (214, 178, 96)          # altın
V.BG = (10, 14, 22)               # gece mavisi-siyah

# --------------------------------------------------------------------------
# Çizim stili: yüzsüz, sinematik, sakin. Peygamber, sahabe, melek ASLA çizilmez.
# --------------------------------------------------------------------------
SC.STYLE = (
    "Cinematic stylized 3D animation still, soft low-poly look, smooth matte surfaces, dramatic volumetric light, "
    "deep night blue and warm gold palette, calm reverent mood, film grain, clear simple composition. "
    "All human figures are smooth faceless mannequin-like characters: blank smooth heads with NO eyes, NO nose, "
    "NO mouth, no facial features at all. Men wear ordinary modest modern clothes (jackets, coats, trousers) and have "
    "bare smooth heads unless a cap is described; a headscarf ONLY on a figure explicitly described as a woman. "
    "Draw exactly the number of people described in the scene; if the scene mentions no person, draw NO people at all. "
    "No angels, no winged beings, no glowing holy figures, no prophets, no religious leaders. "
    "Mosques always have crescent finials, never crosses; no churches, no crosses anywhere. "
    "No text, no letters, no calligraphy, no writing on any surface, no logos. No blood, no injury, no fire on people.")

# İnsansız sahneler ("insan": false) için ayrı stil: figür tarifini hiç içermez, model figür eklemesin.
STYLE_BOS = (
    "Cinematic stylized 3D animation still, soft low-poly look, smooth matte surfaces, dramatic volumetric light, "
    "deep night blue and warm gold palette, calm reverent mood, film grain, clear simple composition. "
    "EMPTY SCENE: absolutely no people, no human figures, no mannequins, no dolls, no figurines, no statues, no silhouettes. "
    "Mosques always have crescent finials, never crosses; no churches, no crosses anywhere. "
    "No text, no letters, no calligraphy, no writing on any surface, no logos.")


def build_prompt(ep, idx):
    sahne = ep["scenes"][idx - 1]
    sc = sahne["prompt"]
    for key, desc in ep.get("characters", {}).items():
        sc = sc.replace("{" + key + "}", desc)
    return f"{sc} {STYLE_BOS if sahne.get('insan') is False else SC.STYLE}"


SC.build_prompt = build_prompt

SC.QA_PROMPT = (
    "You are a strict quality checker for stylized 3D animation stills used in short reverent Islamic reminder "
    "videos. Scene description: \"{desc}\". Look carefully for VISUAL ERRORS: any human figure with visible facial "
    "features (eyes, nose, mouth) counts as a SEVERE error because all figures must be faceless; extra or missing "
    "limbs, deformed hands, objects duplicated when there should be one, objects merging into bodies, floating or "
    "impossible objects, broken perspective, any visible text, letters or calligraphy (severe), any winged or angelic "
    "being (severe), any cross or church symbol (severe), any person, figure, doll or figurine in a scene whose "
    "description says no people (severe), a woman's headscarf on a figure described as a man (severe), "
    "any gore, blood or injury (severe). Ignore artistic style. "
    "Reply ONLY with JSON: {{\"ok\": true/false, \"siddet\": 0-10 (0 = flawless, 10 = unusable), "
    "\"sorun\": \"short description in Turkish or empty\"}}")


# --------------------------------------------------------------------------
# Başlık ve son kart
# --------------------------------------------------------------------------
def header(ep):
    im = Image.new("RGB", (V.W, V.H), V.BG)
    d = ImageDraw.Draw(im)
    f1 = V.font(30)
    t1 = "   ".join(" ".join(k) for k in SERI.split(" "))
    if d.textlength(t1, font=f1) > V.W - 60:
        t1 = SERI
    d.text(((V.W - d.textlength(t1, font=f1)) / 2, 52), t1, font=f1, fill=V.AMBER)
    size = 58
    t2 = V.tr_upper(ep["title"])
    while d.textlength(t2, font=V.font(size)) > V.W - 80 and size > 34:
        size -= 2
    d.text(((V.W - d.textlength(t2, font=V.font(size))) / 2, 104), t2, font=V.font(size), fill=V.WHITE)
    if V.HANDLE:
        fh = V.font(36)
        d.text(((V.W - d.textlength(V.HANDLE, font=fh)) / 2, 1690), V.HANDLE, font=fh, fill=(120, 128, 146))
    return np.asarray(im, np.float32)


def end_card(ep, k):
    im = Image.new("RGB", (V.W, V.H), V.BG)
    d = ImageDraw.Draw(im)
    a = max(0.0, min(1.0, k))
    c = lambda col: tuple(int(V.BG[i] + (v - V.BG[i]) * a) for i, v in enumerate(col))  # noqa: E731
    metin = "“" + ep.get("hisse", "") + "”"
    boy = 60 if len(metin) <= 90 else 50
    f2 = V.font(boy)
    satirlar = V._sar(d, metin, f2, V.W - 160)
    y = 690 if len(satirlar) <= 4 else 560
    f1 = V.font(40)
    t1 = ep.get("kart_baslik", "HADİS-İ ŞERİF")
    d.text(((V.W - d.textlength(t1, font=f1)) / 2, y - 100), t1, font=f1, fill=c(V.AMBER))
    for ln in satirlar:
        d.text(((V.W - d.textlength(ln, font=f2)) / 2, y), ln, font=f2, fill=c((255, 255, 255)))
        y += int(boy * 1.33)
    f3 = V.font(36)
    t3 = ep.get("kaynak", "")
    d.text(((V.W - d.textlength(t3, font=f3)) / 2, y + 40), t3, font=f3, fill=c(V.AMBER))
    t4 = ep.get("son_alt", "Her akşam bir hadis, bir gün")
    d.text(((V.W - d.textlength(t4, font=f3)) / 2, y + 120), t4, font=f3, fill=c((170, 178, 196)))
    if V.HANDLE:
        d.text(((V.W - d.textlength(V.HANDLE, font=f3)) / 2, y + 180), V.HANDLE, font=f3, fill=c((120, 128, 146)))
    return np.asarray(im, np.float32)


def grade(img, sicak=False):
    """Hafif soğuk, sinematik renk; sicak=True sahnelerde altın ışık korunur."""
    k = np.array([1.02, 1.0, 0.94], np.float32) if sicak else np.array([0.96, 0.99, 1.05], np.float32)
    return (img * k - 128) * 1.06 + 126


V.header = header
V.end_card = end_card
V.grade = grade


# --------------------------------------------------------------------------
# Fon müziği: telifsiz, sentetik "uhrevi" dem: ney benzeri nefesli uzun notalar + derin dem.
# --------------------------------------------------------------------------
def _ney(f, dur, sr, rng):
    t = np.arange(int(dur * sr)) / sr
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * t + rng.uniform(0, 6))
    ph = 2 * np.pi * f * np.cumsum(vib) / sr
    ton = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    nefes = rng.normal(0, 1, len(t)).astype(np.float32)
    k = 24
    nefes = np.convolve(nefes, np.ones(k) / k, mode="same") * 0.6
    zarf = np.minimum(1, t / 0.9) * np.minimum(1, (dur - t) / 1.2).clip(0, 1)
    return ((ton * 0.8 + nefes * 0.25) * zarf).astype(np.float32)


def uhrevi(seconds, sr=S.SR, seed=4, sting_at=None):
    rng = np.random.default_rng(seed)
    n = int(seconds * sr) + sr
    out = np.zeros(n, np.float32)
    mid = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    dizi = [62, 63, 65, 67, 69, 70, 72]           # Re merkezli, Uşşak'ı andıran yumuşak dizi
    cumleler = [[4, 3, 2, 1, 0], [0, 2, 3, 4, 3], [5, 4, 3, 2], [2, 1, 0]]
    t, k = 1.2, 0
    while t < seconds - 2:
        cm = cumleler[(k + seed) % len(cumleler)]
        for idx in cm:
            dur = rng.uniform(1.6, 2.4)
            x = _ney(mid(dizi[idx]), dur, sr, rng) * 0.32
            s0 = int(t * sr)
            e = min(n, s0 + len(x))
            if e > s0:
                out[s0:e] += x[: e - s0]
            t += dur * 0.82
        t += 2.2
        k += 1
    tt = np.arange(n) / sr
    dem = (0.22 * np.sin(2 * np.pi * mid(38) * tt) + 0.12 * np.sin(2 * np.pi * mid(45) * tt)
           + 0.05 * np.sin(2 * np.pi * mid(50) * tt)).astype(np.float32)
    dem *= (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * tt)).astype(np.float32)
    out += dem
    out = out[: int(seconds * sr)]
    t2 = np.arange(len(out)) / sr
    out *= np.minimum(1, t2 / 2.0).astype(np.float32)
    return out / (np.abs(out).max() + 1e-6)


S.masal = uhrevi
