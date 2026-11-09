"""Kıssadan Hisse seslendirme + sıcak masal müziği.
Gemini TTS (bölüm başına TEK istek, sahnelere bölünür). Gemini olmazsa bölümün tamamı Piper ile okunur
(yarım yamalak karışık ses olmaz). Müzik tamamen sentetik (telifsiz) karanlık bir uğultu."""
import os
import subprocess
import sys
import wave

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPO = float(os.environ.get("GEMINI_TEMPO", "1.0"))
MUSIC_VOL = float(os.environ.get("MUSIC_VOL", "0.26"))
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse,")
FILTERS = ("highpass=f=70,lowpass=f=11500,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,"
           "loudnorm=I=-16:TP=-1.5:LRA=7")
PIPER = os.environ.get("PIPER_MODEL", os.path.join(ROOT, "models", "tr_TR-fahrettin-medium.onnx"))


def temiz(text):
    from .numbers import seslendirme_metni
    t = text.replace("\n", " ").replace('"', "").replace("“", "").replace("”", "")
    return seslendirme_metni(" ".join(t.split()))


def sure(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def _isle(raw_args, dst):
    af = TRIM + (f"atempo={TEMPO}," if abs(TEMPO - 1) > 0.01 else "") + FILTERS
    subprocess.run(["ffmpeg", "-v", "error", "-y", *raw_args, "-af", af, "-ar", str(SR), "-ac", "1", dst], check=True)


def _gemini(metinler, workdir):
    from . import gemini_ses
    a24, _ = gemini_ses.seslendir(metinler)
    out = []
    for i, part in enumerate(gemini_ses.bol(a24, 24000, metinler), 1):
        raw = os.path.join(workdir, f"v{i}.pcm")
        (np.clip(part, -1, 1) * 32767).astype("<i2").tofile(raw)
        dst = os.path.join(workdir, f"v{i}.wav")
        _isle(["-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw], dst)
        os.remove(raw)
        out.append((dst, sure(dst)))
    return out


def _piper(metinler, workdir):
    out = []
    for i, m in enumerate(metinler, 1):
        raw = os.path.join(workdir, f"p{i}.wav")
        subprocess.run([sys.executable, "-m", "piper", "-m", PIPER, "-f", raw, "--sentence-silence", "0.25"],
                       input=m.encode(), check=True, capture_output=True)
        dst = os.path.join(workdir, f"v{i}.wav")
        _isle(["-i", raw], dst)
        out.append((dst, sure(dst)))
    return out


def sessiz(metinler, workdir):
    """Yerel önizleme: metin uzunluğunda sessizlik."""
    out = []
    for i, m in enumerate(metinler, 1):
        dst = os.path.join(workdir, f"v{i}.wav")
        yaz(dst, np.zeros(int(SR * max(1.5, len(m) * 0.062)), np.float32))
        out.append((dst, sure(dst)))
    return out


def seslendir(satirlar, workdir):
    os.makedirs(workdir, exist_ok=True)
    metinler = [temiz(s) for s in satirlar]
    motor = os.environ.get("TTS_ENGINE", "gemini")
    if motor == "sessiz":
        return sessiz(metinler, workdir)
    if motor == "gemini" and os.environ.get("GEMINI_API_KEY"):
        try:
            return _gemini(metinler, workdir)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::Gemini sesi alınamadı, bölümün tamamı yedek sesle okunacak: {e}", flush=True)
    return _piper(metinler, workdir)


# --------------------------------------------------------------------------
# Masal müziği (sentetik, telifsiz): mızrap tınısı (Karplus-Strong) + yumuşak dem (drone)
# --------------------------------------------------------------------------
def _mizrap(f, dur, sr, rng, parlak=0.5):
    n = int(sr * dur)
    p = max(2, int(sr / f))
    buf = rng.uniform(-1, 1, p).astype(np.float32)
    out = np.zeros(n, np.float32)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.996 * (parlak * buf[i % p] + (1 - parlak) * buf[(i + 1) % p])
    return out * np.exp(-np.arange(n) / (sr * 1.2)).astype(np.float32)


def masal(seconds, sr=SR, seed=4, sting_at=None):
    rng = np.random.default_rng(seed)
    n = int(seconds * sr) + sr
    out = np.zeros(n, np.float32)
    mid = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    # Re (D) merkezli, Uşşak/Hüseyni havasını andıran yumuşak dizi
    dizi = [62, 64, 65, 67, 69, 70, 72, 74]
    motifler = [[4, 3, 2, 1, 0], [0, 1, 2, 4, 3], [4, 5, 4, 3, 2], [2, 1, 0, 1, 0]]
    t, k = 0.6, 0
    cache = {}
    while t < seconds - 1:
        mot = motifler[(k + seed) % len(motifler)]
        for j, idx in enumerate(mot):
            note = dizi[idx]
            if note not in cache:
                cache[note] = _mizrap(mid(note), 1.6, sr, rng)
            x = cache[note] * (0.55 if j else 0.7) * rng.uniform(0.85, 1.0)
            s0 = int((t + j * 0.42 + rng.uniform(-0.015, 0.015)) * sr)
            e = min(n, s0 + len(x))
            if e > s0:
                out[s0:e] += x[: e - s0]
        t += 0.42 * len(mot) + 1.3
        k += 1
    tt = np.arange(n) / sr
    dem = (0.18 * np.sin(2 * np.pi * mid(50) * tt) + 0.1 * np.sin(2 * np.pi * mid(57) * tt)).astype(np.float32)
    dem *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.08 * tt)).astype(np.float32)
    out += dem
    out = out[: int(seconds * sr)]
    t2 = np.arange(len(out)) / sr
    out *= np.minimum(1, t2 / 1.5).astype(np.float32)
    return out / (np.abs(out).max() + 1e-6)


# --------------------------------------------------------------------------
# Gerilim müziği (kullanılmıyor, yedek)
# --------------------------------------------------------------------------
def drone(seconds, sr=SR, seed=4, sting_at=None):
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    for f, a in ((49.0, 0.5), (49.6, 0.4), (24.5, 0.35), (73.4, 0.14), (103.8, 0.06)):
        lfo = 0.7 + 0.3 * np.sin(2 * np.pi * rng.uniform(0.03, 0.09) * t + rng.uniform(0, 6))
        out += (a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * lfo).astype(np.float32)
    noise = rng.normal(0, 1, n).astype(np.float32)
    k = int(sr * 0.004)
    wind = np.convolve(noise, np.ones(k, np.float32) / k, mode="same")
    wind *= (0.5 + 0.5 * np.sin(2 * np.pi * 0.06 * t) ** 2).astype(np.float32)
    out += wind * 0.55
    for _ in range(max(1, int(seconds / 12))):
        s = rng.uniform(2, max(3, seconds - 4))
        i0 = int(s * sr)
        d = np.arange(int(sr * 3.5)) / sr
        ping = (0.11 * np.sin(2 * np.pi * rng.choice([277.2, 311.1, 369.9]) * d) * np.exp(-d * 1.3)).astype(np.float32)
        e = min(n, i0 + len(ping))
        out[i0:e] += ping[: e - i0]
    if sting_at is not None:
        i0 = int(sting_at * sr)
        d = np.arange(int(sr * 2.2)) / sr
        sweep = np.sin(2 * np.pi * (70 + 280 * d ** 2) * d) * (d / 2.2) ** 2 * 0.6
        m = int(sr * 0.25)
        hit = np.zeros_like(d)
        hit[-m:] = rng.normal(0, 1, m) * np.exp(-np.arange(m) / (sr * 0.05))
        seg = (sweep + hit * 0.7).astype(np.float32)
        e = min(n, i0 + len(seg))
        if e > i0:
            out[i0:e] += seg[: e - i0]
    out *= np.minimum(1, t / 2.0).astype(np.float32)
    return out / (np.abs(out).max() + 1e-6)


def yaz(path, a, sr=SR):
    a = np.clip(a, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((a * 32767).astype(np.int16).tobytes())


def oku(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def birlestir(parcalar, baslar, toplam, out_path, workdir, sting_at=None, seed=4):
    """Konuşmaları zamanlarına yerleştirir, altına masal müziği koyar (konuşurken kısılır)."""
    voice = np.zeros(int(toplam * SR) + SR, dtype=np.float32)
    for (path, _), st in zip(parcalar, baslar):
        a = oku(path)
        s = int(st * SR)
        voice[s:s + len(a)] += a[: len(voice) - s]
    voice = voice[: int(toplam * SR)]
    vw = os.path.join(workdir, "voice_full.wav")
    mw = os.path.join(workdir, "music.wav")
    yaz(vw, voice)
    yaz(mw, masal(toplam, SR, seed=seed))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vw, "-i", mw, "-filter_complex",
                    f"[1]lowpass=f=6000,volume={MUSIC_VOL},afade=t=in:d=1.5,"
                    f"afade=t=out:st={max(0.1, toplam - 1.5):.2f}:d=1.4[m];"
                    "[0]asplit=2[v][sc];"
                    "[m][sc]sidechaincompress=threshold=0.03:ratio=3:attack=80:release=600[md];"
                    "[v][md]amix=inputs=2:duration=first:normalize=0", "-ar", str(SR), out_path], check=True)
