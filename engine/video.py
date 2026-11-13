"""Kıssadan Hisse video motoru.
Sahne = 2D çizgi film tarzı yapay zekâ çizimi (hareketli: parallax + parçacık) + sıcak renk + kelime kelime sarı alt yazı.
Kullanım: python -m engine.video <bölüm.json> <resim_klasörü> <çıktı.mp4>"""
import json
import re
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import ses as S

W, H, FPS = 1080, 1920, 30
IMG_Y, IMG_H = 210, 1440
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "fonts", "Poppins-Bold.ttf")
HANDLE = "@kissadan.hisse.tr"
RED = (226, 58, 52)
AMBER = (240, 178, 60)
YELLOW = (255, 214, 10)
BG = (24, 19, 15)
WHITE = (240, 240, 244)
LEAD, GAP, FADE, END = 0.3, 0.35, 0.45, 4.2
CAP_Y = 1360


def font(size):
    return ImageFont.truetype(FONT, size)


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


# --------------------------------------------------------------------------
# Sabit katmanlar
# --------------------------------------------------------------------------
def header(ep):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    f1 = font(30)
    t1 = "K I S S A D A N   H İ S S E"
    d.text(((W - d.textlength(t1, font=f1)) / 2, 52), t1, font=f1, fill=AMBER)
    size = 58
    t2 = tr_upper(ep["title"])
    while d.textlength(t2, font=font(size)) > W - 80 and size > 34:
        size -= 2
    d.text(((W - d.textlength(t2, font=font(size))) / 2, 104), t2, font=font(size), fill=WHITE)
    fh = font(36)
    d.text(((W - d.textlength(HANDLE, font=fh)) / 2, 1690), HANDLE, font=fh, fill=(140, 124, 104))
    return np.asarray(im, np.float32)


def edge_mask():
    m = np.ones((IMG_H, W), np.float32)
    g = 140
    m[:g] *= (np.linspace(0, 1, g) ** 1.5)[:, None]
    m[-260:] *= (np.linspace(1, 0, 260) ** 1.2)[:, None]
    yy, xx = np.mgrid[0:IMG_H, 0:W].astype(np.float32)
    dist = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - IMG_H / 2) / (IMG_H * 0.62)) ** 2)
    vig = np.clip(1.12 - dist ** 2 * 0.3, 0.55, 1.0)
    return m[..., None], vig[..., None]


def grains(n=6, seed=9):
    rng = np.random.default_rng(seed)
    return [rng.normal(0, 2.5, (IMG_H // 2, W // 2)).astype(np.float32).repeat(2, 0).repeat(2, 1)[..., None]
            for _ in range(n)]


class Fog:
    """Dikişsiz (periyodik) yavaş akan sis dokusu."""

    def __init__(self, h=IMG_H, w=W, seed=3):
        rng = np.random.default_rng(seed)
        fy = np.fft.fftfreq(h)[:, None]
        fx = np.fft.fftfreq(w)[None, :]
        acc = np.zeros((h, w), np.float32)
        for sigma, wgt in ((16, 0.45), (45, 0.35), (110, 0.2)):
            n = rng.random((h, w)).astype(np.float32)
            b = np.real(np.fft.ifft2(np.fft.fft2(n) * np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))))
            acc += ((b - b.mean()) / (b.std() + 1e-6)).astype(np.float32) * wgt
        acc = np.clip((np.clip(0.5 + acc * 0.32, 0, 1) - 0.35) * 2.0, 0, 1)
        self.tex = np.concatenate([acc, acc], axis=1)
        self.w = w
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        self.band = np.clip((yy - 0.25) / 0.6, 0.2, 1.0)

    def alpha(self, t, k):
        o1 = int((t * 22) % self.w)
        o2 = int((t * 9 + self.w / 2) % self.w)
        a = 0.6 * self.tex[:, o1:o1 + self.w] + 0.4 * self.tex[::-1, o2:o2 + self.w]
        return (a * self.band * k)[..., None]


def grade(img, sicak=False):
    img = img * np.array([1.03, 1.0, 0.95], np.float32)
    return (img - 128) * 1.04 + 130


# --------------------------------------------------------------------------
# Alt yazı
# --------------------------------------------------------------------------
def word_times(text, start, dur):
    words = text.split()
    w = [len(x) + 2 for x in words]
    tot = sum(w)
    out, t = [], start
    for x, k in zip(words, w):
        d = dur * k / tot
        out.append((x, t, t + d))
        t += d
    return out


def chunks(timed, maxw=W - 140, size=62):
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = font(size)
    res, cur = [], []
    for item in timed:
        trial = " ".join(x for x, _, _ in cur + [item])
        if cur and (d.textlength(trial, font=f) > maxw or len(cur) >= 4 or cur[-1][0][-1] in ".!?:"):
            res.append(cur)
            cur = []
        cur.append(item)
    if cur:
        res.append(cur)
    return res


_CAP = {}


def caption_layer(ch, hi, size=66):
    key = (id(ch), hi)
    if key in _CAP:
        return _CAP[key]
    f = font(size)
    lay = Image.new("RGBA", (W, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    words = [x for x, _, _ in ch]
    sp = d.textlength(" ", font=f)
    widths = [d.textlength(x, font=f) for x in words]
    x = (W - (sum(widths) + sp * (len(words) - 1))) / 2
    for i, (wd, wtxt) in enumerate(zip(widths, words)):
        col = YELLOW if i == hi else (255, 255, 255)
        d.text((x, 24), wtxt, font=f, fill=col + (255,), stroke_width=7, stroke_fill=(20, 14, 8, 255))
        x += wd + sp
    arr = np.asarray(lay, np.float32)
    _CAP[key] = arr
    return arr


def paste(frame, lay, y, alpha=1.0):
    h = lay.shape[0]
    a = lay[..., 3:4] / 255 * alpha
    frame[y:y + h] = frame[y:y + h] * (1 - a) + lay[..., :3] * a


def tag_layer(text):
    f = font(30)
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = int(d.textlength(text, font=f))
    lay = Image.new("RGBA", (tw + 40, 56), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, 0, tw + 39, 55], 12, fill=(30, 22, 14, 210), outline=AMBER + (255,), width=3)
    d.text((20, 9), text, font=f, fill=WHITE + (255,))
    return np.asarray(lay, np.float32)


def _sar(d, metin, f, maxw):
    satirlar, cur = [], ""
    for w in metin.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > maxw and cur:
            satirlar.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        satirlar.append(cur)
    return satirlar


# --------------------------------------------------------------------------
# 0. saniye kanca yazısı (13 Kasım): sessiz izleyen de ilk karede ne olduğunu anlasın
# --------------------------------------------------------------------------
KANCA_SURE, ZOOM_SURE = 3.0, 0.8


def kanca_metni(ep):
    """Bölümde "kanca_yazi" varsa o; yoksa açıklamanın ilk satırı (zaten kanca olarak yazılıyor)."""
    t = (ep.get("kanca_yazi") or "").strip()
    if not t:
        t = ((ep.get("caption") or ep.get("instagram_caption") or "").strip().split("\n") or [""])[0]
    t = "".join(ch for ch in t if ord(ch) < 0x2190 or ch in "…’‘“”–—").strip()
    t = " ".join(t.split())
    if len(t) > 60:                      # uzunsa sadece ilk cümle
        m = re.match(r"(.+?[.?!…])(\s|$)", t)
        if m and len(m.group(1)) >= 15:
            t = m.group(1)
    w = t.split()
    if len(w) > 18:
        t = " ".join(w[:17]) + "…"
    return t


def _kanca_sar(d, metin, f, maxw):
    satirlar, cur = [], ""
    for w in metin.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) > maxw and cur:
            satirlar.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        satirlar.append(cur)
    return satirlar


def kanca_layer(text, size=78):
    if not text:
        return None
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    while size > 54:
        lines = _kanca_sar(d, text, font(size), W - 170)
        if len(lines) <= 3:
            break
        size -= 4
    f = font(size)
    lh = int(size * 1.25)
    h = lh * len(lines) + 70
    lay = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(lay)
    bw = max(dd.textlength(ln, font=f) for ln in lines) + 90
    dd.rounded_rectangle([(W - bw) / 2, 0, (W + bw) / 2, h - 1], 34, fill=(8, 8, 10, 175))
    y = 35
    for ln in lines:
        dd.text(((W - dd.textlength(ln, font=f)) / 2, y), ln, font=f, fill=(255, 255, 255, 255),
                stroke_width=6, stroke_fill=(10, 8, 6, 255))
        y += lh
    return np.asarray(lay, np.float32)


def zoom_region(region, t):
    """İlk 0,8 sn: %14 yakından başlayıp normale inen hızlı zoom (kalıp kırma)."""
    if t >= ZOOM_SURE:
        return region
    k = 1 - (1 - t / ZOOM_SURE) ** 3
    z = 1.14 - 0.14 * k
    h, w = region.shape[:2]
    ch, cw = int(h / z), int(w / z)
    y0, x0 = (h - ch) // 2, (w - cw) // 2
    crop = Image.fromarray(region[y0:y0 + ch, x0:x0 + cw].clip(0, 255).astype(np.uint8))
    return np.asarray(crop.resize((w, h), Image.BILINEAR), np.float32)


def end_card(ep, k):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    a = max(0.0, min(1.0, k))
    c = lambda col: tuple(int(BG[i] + (v - BG[i]) * a) for i, v in enumerate(col))  # noqa: E731
    f1 = font(44)
    t1 = "KISSADAN HİSSE"
    d.text(((W - d.textlength(t1, font=f1)) / 2, 640), t1, font=f1, fill=c(AMBER))
    f2 = font(64)
    y = 740
    for ln in _sar(d, ep.get("hisse", ""), f2, W - 160):
        d.text(((W - d.textlength(ln, font=f2)) / 2, y), ln, font=f2, fill=c((255, 255, 255)))
        y += 84
    f3 = font(38)
    t3 = ep.get("son_alt", "Her akşam 21:30'da yeni kıssa")
    d.text(((W - d.textlength(t3, font=f3)) / 2, y + 60), t3, font=f3, fill=c((200, 186, 160)))
    d.text(((W - d.textlength(HANDLE, font=f3)) / 2, y + 120), HANDLE, font=f3, fill=c((150, 136, 116)))
    return np.asarray(im, np.float32)


# --------------------------------------------------------------------------
# Ana akış
# --------------------------------------------------------------------------
def plan(durs):
    starts, t = [], LEAD
    for d in durs:
        starts.append(t)
        t += d + GAP
    return starts, round(t + 0.6, 2)


def render_episode(ep_path, img_dir, out):
    from .motion import SceneMotion
    ep = json.load(open(ep_path, encoding="utf-8"))
    work = os.path.join(os.path.dirname(os.path.abspath(out)), "work_" + ep["id"])
    os.makedirs(work, exist_ok=True)
    sc = ep["scenes"]
    parts = S.seslendir([s.get("say", s["text"]) for s in sc], work)
    starts, speech_end = plan([d for _, d in parts])
    total = speech_end + END
    audio = os.path.join(work, "audio.wav")
    S.birlestir(parts, starts, total, audio, work, seed=int(ep["id"]) + 7)
    print(f"Süre: {total:.1f} sn", flush=True)

    hdr = header(ep)
    klay = kanca_layer(kanca_metni(ep))
    kbit = max(2.2, min(KANCA_SURE, starts[0] + parts[0][1]))
    emask, vig = edge_mask()
    gr = grains()
    fog = Fog()
    prepared = []
    for i, (s, st, (_, d)) in enumerate(zip(sc, starts, parts)):
        img = os.path.join(img_dir, f"sahne{i + 1}.png")
        mot = SceneMotion(img, s.get("prompt", ""), W, IMG_H, seed=i + 1)
        p = (s.get("prompt", "") or "").lower()
        sis = s.get("sis", 0.0)
        prepared.append({"t": 0.0 if i == 0 else st - 0.3, "mot": mot, "sis": sis, "sicak": s.get("sicak", False),
                         "caps": chunks(word_times(s["text"], st, d)),
                         "tag": tag_layer(s["yer"]) if s.get("yer") else None})
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                           "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    n = int(total * FPS)
    for fi in range(n):
        t = fi / FPS
        if t >= speech_end:
            k = (t - speech_end) / 0.6
            ff.stdin.write(end_card(ep, k).clip(0, 255).astype(np.uint8).tobytes())
            continue
        idx = max(i for i, p in enumerate(prepared) if p["t"] <= t)
        frame = hdr.copy()
        region = np.zeros((IMG_H, W, 3), np.float32)
        layers = []
        if idx > 0 and t - prepared[idx]["t"] < FADE:
            layers.append((idx - 1, 1.0))
            layers.append((idx, (t - prepared[idx]["t"]) / FADE))
        else:
            layers.append((idx, 1.0))
        for j, a in layers:
            p = prepared[j]
            nxt = prepared[j + 1]["t"] if j + 1 < len(prepared) else speech_end
            img = grade(p["mot"].frame(t - p["t"], (t - p["t"]) / max(0.5, nxt - p["t"] + FADE)), p["sicak"])
            if p["sis"] > 0:
                fa = fog.alpha(t, p["sis"])
                img = img * (1 - fa) + np.array([236, 226, 205], np.float32) * fa
            region = region * (1 - a) + img * a
        region = region * vig + gr[fi % len(gr)]
        region = zoom_region(region, t)
        frame[IMG_Y:IMG_Y + IMG_H] = frame[IMG_Y:IMG_Y + IMG_H] * (1 - emask) + region * emask
        cur = prepared[idx]
        if cur["tag"] is not None:
            ta = min(1.0, max(0.0, (t - cur["t"] - 0.2) / 0.4))
            th, tw = cur["tag"].shape[:2]
            sub = frame[IMG_Y + 40:IMG_Y + 40 + th, 40:40 + tw]
            al = cur["tag"][..., 3:4] / 255 * ta
            frame[IMG_Y + 40:IMG_Y + 40 + th, 40:40 + tw] = sub * (1 - al) + cur["tag"][..., :3] * al
        for ch in ([] if (klay is not None and t < kbit - 0.3) else cur["caps"]):
            if ch[0][1] - 0.05 <= t <= ch[-1][2] + 0.2:
                hi = max([i for i, (_, s0, _) in enumerate(ch) if s0 <= t] or [0])
                paste(frame, caption_layer(ch, hi), CAP_Y)
                break
        if klay is not None and t < kbit:
            paste(frame, klay, IMG_Y + int(IMG_H * 0.36), min(1.0, (kbit - t) / 0.3))
        ff.stdin.write(frame.clip(0, 255).astype(np.uint8).tobytes())
        if fi % 300 == 0:
            print(f"  kare {fi}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"Hazır: {out} ({total:.1f} sn)")


if __name__ == "__main__":
    render_episode(sys.argv[1], sys.argv[2], sys.argv[3])
