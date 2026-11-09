"""Kıssadan Hisse (Bir Satır Hayat motorundan): durağan sahne görsellerine hareket katar.

- 2.5D parallax: derinlik haritasıyla (Depth Anything V2 Small, yoksa basit tahmin) ön plan ve arka plan
  farklı hızda kayar, kamera yavaşça yakınlaşır.
- Rüzgâr: yapraklık renkli (yeşil/sarı/turuncu) ve uzak bölgeler hafifçe salınır.
- Parçacıklar: sahne tarifine göre yağmur, kar, düşen yaprak ya da süzülen ışık zerreleri.
Hepsi CPU'da, ücretsiz araçlarla çalışır."""
import math
import os

import cv2
import numpy as np
from PIL import Image

_DEPTH = {"pipe": None, "tried": False}


def _depth_model(im):
    """0 = uzak, 1 = yakın. Model yoksa ya da hata verirse None."""
    if os.environ.get("NO_DEPTH_MODEL"):
        return None
    if not _DEPTH["tried"]:
        _DEPTH["tried"] = True
        try:
            from transformers import pipeline
            _DEPTH["pipe"] = pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf", device="cpu")
            print("Derinlik: Depth Anything V2 Small")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::Derinlik modeli yüklenemedi, basit tahmin kullanılacak: {e}")
    if _DEPTH["pipe"] is None:
        return None
    try:
        d = np.asarray(_DEPTH["pipe"](im)["depth"], np.float32)
        d = cv2.resize(d, im.size, interpolation=cv2.INTER_CUBIC)
        return (d - d.min()) / (d.max() - d.min() + 1e-6)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::Derinlik hesaplanamadı: {e}")
        return None


def _depth_guess(rgb):
    """Model yoksa: aşağısı yakın, yukarısı uzak; keskin ve doygun bölgeler biraz daha yakın."""
    h, w = rgb.shape[:2]
    grad = np.linspace(0.15, 1.0, h, dtype=np.float32)[:, None].repeat(w, 1) ** 1.3
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    detail = cv2.GaussianBlur(np.abs(cv2.Laplacian(gray, cv2.CV_32F)), (0, 0), 25)
    detail /= detail.max() + 1e-6
    d = 0.75 * grad + 0.25 * detail
    return (d - d.min()) / (d.max() - d.min() + 1e-6)


def _effects(prompt):
    p = (prompt or "").lower()
    fx = set()
    if any(k in p for k in ("rain", "storm", "drizzle")):
        fx.add("rain")
    if any(k in p for k in ("snow", "winter")):
        fx.add("snow")
    if any(k in p for k in ("autumn", "fall ", "leaves", "falling leaf")):
        fx.add("leaves")
    if any(k in p for k in ("blossom", "petal", "spring", "cherry")):
        fx.add("petals")
    if any(k in p for k in ("night", "candle", "lamp", "lantern", "firefl", "stars")):
        fx.add("glow")
    if not fx & {"rain", "snow", "leaves", "petals"}:
        fx.add("motes")
    if any(k in p for k in ("tree", "forest", "park", "garden", "leaves", "plant", "flower", "field", "grass")):
        fx.add("sway")
    return fx


class SceneMotion:
    def __init__(self, path, prompt, out_w, out_h, seed=0, strength=1.0):
        self.W, self.H = out_w, out_h
        self.fx = _effects(prompt)
        self.k = strength
        self.rng = np.random.default_rng(seed)
        im = Image.open(path).convert("RGB")
        # zoom ve kayma payı için çıktıdan %18 büyük hazırla
        pad = 1.18
        sc = max(out_w * pad / im.width, out_h * pad / im.height)
        big = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        self.src = np.asarray(big, np.float32)
        self.sh, self.sw = self.src.shape[:2]
        d = _depth_model(big)
        self.depth = d if d is not None else _depth_guess(self.src.astype(np.uint8))
        self.depth = cv2.GaussianBlur(self.depth.astype(np.float32), (0, 0), 3)
        # rüzgâr maskesi: yapraklık renkler, uzak ve görselin üst yarısında ağırlıklı
        hsv = cv2.cvtColor(self.src.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
        hue, sat = hsv[..., 0], hsv[..., 1] / 255
        leafy = (((hue >= 8) & (hue <= 85)) & (sat > 0.28)).astype(np.float32)
        far = np.clip(1.3 - self.depth * 1.6, 0, 1)
        top = np.linspace(1, 0.25, self.sh, dtype=np.float32)[:, None]
        self.sway = cv2.GaussianBlur((leafy * far * top).astype(np.float32), (0, 0), 6) if "sway" in self.fx else None
        # kamera yönü sahneye göre değişsin
        self.dir = self.rng.choice([-1, 1])
        self.vy = self.rng.uniform(-0.4, 0.4)
        yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
        self.yy, self.xx = yy, xx
        self._parts = self._init_particles()

    # ---------------- kamera + parallax + rüzgâr ----------------
    def _warp(self, t, prog):
        W, H = self.W, self.H
        z = 1.0 + 0.10 * self.k * _ease(prog)                 # yavaş yakınlaşma
        cx = self.sw / 2 + self.dir * 0.035 * self.sw * self.k * (prog - 0.5)
        cy = self.sh / 2 + self.vy * 0.03 * self.sh * self.k * (prog - 0.5)
        base_scale = min(self.sw / W, self.sh / H) / 1.17 / z
        mx = cx + (self.xx - W / 2) * base_scale
        my = cy + (self.yy - H / 2) * base_scale
        mx, my = mx.astype(np.float32), my.astype(np.float32)
        dmap = cv2.remap(self.depth, mx, my, cv2.INTER_LINEAR)
        # parallax: yakın bölgeler kameranın tersine biraz daha fazla kayar
        px = self.dir * 26 * self.k * (prog - 0.5) * (dmap - 0.45)
        py = 10 * self.k * math.sin(prog * math.pi) * (dmap - 0.45)
        mx = (mx + px).astype(np.float32)
        my = (my + py).astype(np.float32)
        if self.sway is not None:
            s = cv2.remap(self.sway, mx, my, cv2.INTER_LINEAR)
            ph = self.xx * 0.018 + self.yy * 0.011
            mx = mx + s * 4.5 * self.k * (np.sin(t * 1.7 + ph) + 0.4 * np.sin(t * 3.1 + ph * 1.7))
            my = my + s * 1.6 * self.k * np.sin(t * 2.3 + ph * 0.8)
            mx, my = mx.astype(np.float32), my.astype(np.float32)
        return cv2.remap(self.src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

    # ---------------- parçacıklar ----------------
    def _init_particles(self):
        r, W, H = self.rng, self.W, self.H
        P = {}
        if "rain" in self.fx:
            n = 260
            P["rain"] = dict(x=r.uniform(0, W, n), y=r.uniform(0, H, n), v=r.uniform(1300, 1900, n),
                             l=r.uniform(18, 42, n), a=r.uniform(0.25, 0.55, n))
        if "snow" in self.fx:
            n = 160
            P["snow"] = dict(x=r.uniform(0, W, n), y=r.uniform(0, H, n), v=r.uniform(40, 110, n),
                             s=r.uniform(2, 6, n), ph=r.uniform(0, 6.3, n))
        for kind, cols in (("leaves", [(214, 120, 40), (232, 170, 60), (190, 80, 35), (205, 150, 70)]),
                           ("petals", [(246, 196, 206), (250, 220, 226), (238, 170, 186)])):
            if kind in self.fx:
                n = 24 if kind == "leaves" else 26
                P[kind] = dict(x=r.uniform(-50, W, n), y=r.uniform(-H, H, n), v=r.uniform(60, 140, n),
                               s=r.uniform(12, 22, n), ph=r.uniform(0, 6.3, n), spin=r.uniform(-2.5, 2.5, n),
                               c=[cols[i % len(cols)] for i in range(n)])
        if "motes" in self.fx or "glow" in self.fx:
            n = 40 if "glow" in self.fx else 28
            P["motes"] = dict(x=r.uniform(0, W, n), y=r.uniform(0, H, n), v=r.uniform(8, 25, n),
                              s=r.uniform(2, 5, n), ph=r.uniform(0, 6.3, n),
                              warm="glow" in self.fx)
        return P

    def _particles(self, img, t):
        W, H = self.W, self.H
        over = np.zeros((H, W, 3), np.float32)
        alpha = np.zeros((H, W), np.float32)
        P = self._parts
        if "rain" in P:
            q = P["rain"]
            ys = (q["y"] + q["v"] * t) % (H + 60) - 30
            xs = (q["x"] - 0.18 * q["v"] * t) % W
            lay = np.zeros((H, W), np.float32)
            for x, y, l, a in zip(xs, ys, q["l"], q["a"]):
                cv2.line(lay, (int(x), int(y)), (int(x - 0.18 * l), int(y + l)), float(a), 2, cv2.LINE_AA)
            lay = cv2.GaussianBlur(lay, (0, 0), 0.8)
            over += lay[..., None] * np.array([225, 232, 240], np.float32)
            alpha = np.maximum(alpha, lay)
            img = img * (1 - 0.06) + np.array([150, 160, 175], np.float32) * 0.06   # yağmurlu hava tonu
        if "snow" in P:
            q = P["snow"]
            ys = (q["y"] + q["v"] * t) % (H + 20) - 10
            xs = (q["x"] + 18 * np.sin(t * 0.9 + q["ph"])) % W
            lay = np.zeros((H, W), np.float32)
            for x, y, s in zip(xs, ys, q["s"]):
                cv2.circle(lay, (int(x), int(y)), int(s), 0.9, -1, cv2.LINE_AA)
            lay = cv2.GaussianBlur(lay, (0, 0), 1.2)
            over += lay[..., None] * 255
            alpha = np.maximum(alpha, lay)
        for kind in ("leaves", "petals"):
            if kind not in P:
                continue
            q = P[kind]
            for i in range(len(q["x"])):
                y = (q["y"][i] + q["v"][i] * t) % (H + 80) - 40
                x = (q["x"][i] + 40 * math.sin(t * 1.1 + q["ph"][i]) + 25 * t) % (W + 60) - 30
                ang = math.degrees(q["spin"][i] * t + q["ph"][i])
                s = q["s"][i]
                sq = abs(math.cos(t * 2.2 + q["ph"][i]))      # yaprağın dönerken incelmesi
                lay = np.zeros((H, W), np.float32)
                cv2.ellipse(lay, (int(x), int(y)), (int(s), max(2, int(s * 0.45 * (0.35 + 0.65 * sq)))),
                            ang, 0, 360, 0.95, -1, cv2.LINE_AA)
                over += lay[..., None] * np.array(q["c"][i], np.float32)
                alpha = np.maximum(alpha, lay)
        if "motes" in P:
            q = P["motes"]
            ys = (q["y"] - q["v"] * t) % H
            xs = (q["x"] + 14 * np.sin(t * 0.6 + q["ph"])) % W
            lay = np.zeros((H, W), np.float32)
            for x, y, s, ph in zip(xs, ys, q["s"], q["ph"]):
                tw = 0.35 + 0.35 * (1 + math.sin(t * 2.0 + ph)) / 2
                cv2.circle(lay, (int(x), int(y)), int(s), tw, -1, cv2.LINE_AA)
            lay = cv2.GaussianBlur(lay, (0, 0), 3.0) * 1.6
            col = np.array([255, 214, 150] if q["warm"] else [255, 246, 225], np.float32)
            img = img + lay[..., None] * col * 0.55                          # ışık: ekleyerek parlat
        a3 = np.clip(alpha, 0, 1)[..., None]
        return img * (1 - a3) + np.where(a3 > 0, over / np.maximum(a3, 1e-3), 0) * a3

    def frame(self, t, prog):
        """t: sahne başından beri saniye, prog: 0..1 sahne ilerlemesi. (H, W, 3) float32 döner."""
        img = self._warp(t, min(1.0, max(0.0, prog)))
        return np.clip(self._particles(img, t), 0, 255)


def _ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)
