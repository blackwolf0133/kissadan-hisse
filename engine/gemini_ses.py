"""Google Gemini ile seslendirme: BÖLÜM BAŞINA TEK İSTEK.

Bütün sahne metinleri tek seferde okutulur (ses ve ton baştan sona aynı kalır, ücretsiz kotaya sığar),
sonra ses, her sahnenin metin uzunluğuna göre beklenen yerlere en yakın duraklamalardan kesilerek
sahnelere bölünür. Ortam: GEMINI_API_KEY, GEMINI_VOICE, GEMINI_TTS_MODELS (isteğe bağlı)."""
import base64
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np

SR_GEM = 24000
VARSAYILAN_MODELLER = "gemini-3.8-flash-lite-tts,gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts"


def _istek(model, metin, ses, key, dil=True):
    """Sadece okunacak metin gider (talimat okunmasın diye); Türkçe telaffuz dil koduyla sabitlenir."""
    sc = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": ses}}}
    if dil:
        sc["languageCode"] = "tr-TR"            # Türkçe telaffuzu sabitle
    govde = {"generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": sc},
             # TTS modelleri gönderilen her metni okuyor: talimat YOK, sadece hikâye metni gider.
             "contents": [{"role": "user", "parts": [{"text": metin}]}]}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(govde).encode(), headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=240))
    return base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])


def _seslendir_bir(metinler, ton=None):
    """Tüm metinleri tek istekte okutur. (24 kHz float32 dizi, kullanılan model) döner; olmazsa RuntimeError."""
    key = os.environ["GEMINI_API_KEY"]
    ses = os.environ.get("GEMINI_VOICE", "Puck")
    modeller = [m.strip() for m in os.environ.get("GEMINI_TTS_MODELS", VARSAYILAN_MODELLER).split(",") if m.strip()]
    metin = "\n\n".join(metinler)
    dil = True
    son = None
    for model in modeller:
        for deneme in range(3):
            try:
                pcm = _istek(model, metin, ses, key, dil)
                print(f"Gemini sesi: {model}, {ses} (tek istek, {len(metinler)} sahne)", flush=True)
                return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768, model
            except urllib.error.HTTPError as e:
                msg = e.read().decode()[:300]
                son = f"{model}: HTTP {e.code} {msg}"
                print(f"::warning::{son}", flush=True)
                if e.code == 400 and dil and "language" in msg.lower():
                    dil = False                # model dil kodunu desteklemiyorsa onsuz tekrar dene
                    continue
                if e.code == 429 and "minute" not in msg.lower():
                    break                      # günlük kota dolu: sıradaki modele geç
                if e.code in (429, 500, 503):
                    time.sleep(15 * (deneme + 1))
                    continue
                break
            except (KeyError, IndexError, TimeoutError, urllib.error.URLError) as e:
                son = f"{model}: {e}"
                print(f"::warning::{son}", flush=True)
                time.sleep(3)
    raise RuntimeError(son)


def bol(a, sr, metinler, min_sessizlik=0.16):
    """Sesi len(metinler) parçaya böler. Kesimler: uzun duraklamalar, metin uzunluğuna göre beklenen yere yakın."""
    n = len(metinler)
    if n <= 1:
        return [a]
    hop = int(sr * 0.01)
    rms = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, mode="same"))[::hop]
    konusma = rms[rms > np.percentile(rms, 60)]
    esik = max(0.006, (np.median(konusma) if len(konusma) else 0.05) * 0.08)
    sessiz = rms < esik
    adaylar, bas = [], None                       # (orta_nokta_sn, uzunluk_sn)
    for i, s in enumerate(np.append(sessiz, False)):
        if s and bas is None:
            bas = i
        elif not s and bas is not None:
            if (i - bas) * 0.01 >= min_sessizlik and bas > 0 and i < len(sessiz):
                adaylar.append(((bas + i) / 2 * 0.01, (i - bas) * 0.01))
            bas = None
    if len(adaylar) < n - 1:
        raise ValueError(f"{n} sahne için yeterli duraklama yok ({len(adaylar)} bulundu)")
    T = len(a) / sr
    uz = np.array([max(1, len(m)) for m in metinler], float)
    beklenen = np.cumsum(uz)[:-1] / uz.sum() * T          # her sahne sonunun beklenen zamanı
    # dinamik programlama: n-1 artan kesim; puan = duraklama uzunluğu - sapma cezası
    m, K, LAM = len(adaylar), n - 1, 0.12
    NEG = -1e9
    puan = np.full((K, m), NEG)
    geri = np.zeros((K, m), int)
    for j, (t, L) in enumerate(adaylar):
        puan[0, j] = L - LAM * abs(t - beklenen[0])
    for k in range(1, K):
        en_iyi, en_iyi_j = NEG, -1
        for j, (t, L) in enumerate(adaylar):
            if j >= 1 and puan[k - 1, j - 1] > en_iyi:
                en_iyi, en_iyi_j = puan[k - 1, j - 1], j - 1
            if en_iyi_j >= 0:
                puan[k, j] = en_iyi + L - LAM * abs(t - beklenen[k])
                geri[k, j] = en_iyi_j
    j = int(np.argmax(puan[K - 1]))
    secim = [j]
    for k in range(K - 1, 0, -1):
        j = geri[k, j]
        secim.append(j)
    kesim = [int(adaylar[j][0] * sr) for j in reversed(secim)]
    sinir = [0] + kesim + [len(a)]
    return [a[sinir[i]:sinir[i + 1]] for i in range(n)]


# ---------------- okunuş kontrolü ----------------
_W = {"model": None}


def _norm(t):
    import re
    try:
        from .numbers import seslendirme_metni
        t = seslendirme_metni(t)
    except Exception:  # noqa: BLE001
        pass
    t = re.sub(r"\[[^\]]*\]", " ", t)              # [yumuşak] gibi ses etiketlerini karşılaştırmaya katma
    t = t.replace("İ", "i").replace("I", "ı").lower()
    t = re.sub(r"[^a-zçğıöşü0-9 ]+", " ", t)
    return t.split()


def puanla(a, sr, metinler):
    """Sesi yazıya döker, metinle karşılaştırır. (genel benzerlik, ilk cümle benzerliği, döküm) ya da None."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    import difflib, subprocess, tempfile
    if _W["model"] is None:
        _W["model"] = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        yol = f.name
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-", yol],
                   input=pcm, check=True)
    segs, _ = _W["model"].transcribe(yol, language="tr", beam_size=5)
    dokum = " ".join(x.text.strip() for x in segs)
    os.remove(yol)
    bek, gel = "".join(_norm(" ".join(metinler))), "".join(_norm(dokum))   # harf bazlı, boşluksuz
    genel = difflib.SequenceMatcher(None, bek, gel, autojunk=False).ratio()
    ilk = "".join(_norm(metinler[0]))
    ilk_puan = max(difflib.SequenceMatcher(None, ilk, gel[:len(ilk) + k], autojunk=False).ratio() for k in range(-3, 4))
    return genel, ilk_puan, dokum


def seslendir(metinler, ton=None):
    """Seslendirir, yazıya döküp kontrol eder; yanlış okunduysa yeniden üretir (en fazla GEMINI_DENEME kez),
    en doğru okunan sürümü döner."""
    deneme = int(os.environ.get("GEMINI_DENEME", "3"))
    en_iyi = None
    for i in range(deneme):
        a, model = _seslendir_bir(metinler, ton)
        p = puanla(a, SR_GEM, metinler)
        if p is None:
            print("Okunuş kontrolü atlandı (faster-whisper yok)", flush=True)
            return a, model
        genel, ilk, dokum = p
        print(f"Okunuş kontrolü {i + 1}/{deneme}: genel %{genel * 100:.0f}, ilk cümle %{ilk * 100:.0f}", flush=True)
        print(f"  döküm: {dokum[:300]}", flush=True)
        skor = min(genel, ilk)
        if en_iyi is None or skor > en_iyi[0]:
            en_iyi = (skor, a, model)
        if genel >= 0.9 and ilk >= 0.97:
            break
    return en_iyi[1], en_iyi[2]
