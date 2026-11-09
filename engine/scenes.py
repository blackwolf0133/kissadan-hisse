"""Kıssadan Hisse sahne çizimi: FLUX.2-klein-4B (Apache-2.0), stable-diffusion.cpp ile CPU'da.
Kullanım: python -m engine.scenes <bölüm.json> <sahne_no> <sd-cli yolu> <çıktı_klasörü>"""
import os, re, sys, time, subprocess
from huggingface_hub import list_repo_files, hf_hub_download

MODEL = {
    "diffusion": [("leejet/FLUX.2-klein-4B-GGUF", r"Q4_0\.gguf$")],
    "llm": [("unsloth/Qwen3-4B-GGUF", r"Q4_K_M\.gguf$")],
    "vae": [("Comfy-Org/flux2-klein-4B", r"vae/.*\.safetensors$")],
    "steps": 4,
}
STYLE = ("Flat 2D cartoon illustration in a classic storybook animation style, bold clean dark outlines, "
         "simple shapes, warm earthy palette (ochre, terracotta, olive, cream), soft textured paper background, "
         "expressive friendly characters, clear readable composition, traditional old-time Anatolian / Middle Eastern "
         "folk-tale setting with period clothing (robes, vests, şalvar, headscarves, turbans, fezzes), "
         "no modern clothes, no suits, no modern objects, no text, no letters.")
WIDTH, HEIGHT = 768, 1024


def fetch(cands):
    for repo, pat in cands:
        files = list_repo_files(repo)
        hits = sorted(f for f in files if re.search(pat, f))
        if hits:
            return hf_hub_download(repo, hits[0])
    raise SystemExit(f"model bulunamadı: {cands}")


def build_prompt(ep, idx):
    sc = ep["scenes"][idx - 1]["prompt"]
    for key, desc in ep.get("characters", {}).items():
        sc = sc.replace("{" + key + "}", desc)
    return f"{sc} {STYLE}"


QA_PROMPT = (
    "You are a strict quality checker for flat 2D cartoon storybook illustrations used in short fable videos. "
    "Scene description: \"{desc}\". Look carefully for VISUAL ERRORS: extra or missing fingers/limbs, "
    "deformed hands or faces, objects duplicated when there should be one (e.g. two cups, two heads), objects "
    "merging into or coming out of bodies or clothing, floating or impossible objects, broken perspective, "
    "liquid or items in impossible places, any visible text or letters, any gore, blood, corpses or graphic injury "
    "(these count as severe errors). Ignore artistic style. "
    "Reply ONLY with JSON: {{\"ok\": true/false, \"siddet\": 0-10 (0 = flawless, 10 = unusable), "
    "\"sorun\": \"short description in Turkish or empty\"}}")


def _qa_modeller(key):
    """Önce ortamdaki liste, sonra Google'ın güncel listesinden görsel anlayan flash modelleri."""
    import json, urllib.request
    adlar = [m.strip() for m in os.environ.get("GEMINI_QA_MODELS", "gemini-3.8-flash").split(",") if m.strip()]
    try:
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                     headers={"x-goog-api-key": key})
        for m in json.load(urllib.request.urlopen(req, timeout=30)).get("models", []):
            ad = m["name"].split("/")[-1]
            if ("flash" in ad and "generateContent" in m.get("supportedGenerationMethods", [])
                    and not any(x in ad for x in ("tts", "image", "live", "audio", "embedding", "thinking"))
                    and ad not in adlar):
                adlar.append(ad)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::Model listesi alınamadı: {e}", flush=True)
    return adlar[:6]


def kalite(png, desc):
    """Gemini görsel modeliyle hata kontrolü. (ok, şiddet, sorun) ya da kontrol yapılamazsa None."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    import base64, json, urllib.error, urllib.request
    img = base64.b64encode(open(png, "rb").read()).decode()
    for model in _qa_modeller(key):
        body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/png", "data": img}},
                                        {"text": QA_PROMPT.format(desc=desc)}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
        for deneme in range(3):
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    data=json.dumps(body).encode(), headers={"x-goog-api-key": key, "Content-Type": "application/json"})
                r = json.load(urllib.request.urlopen(req, timeout=120))
                j = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
                print(f"  görsel kontrol modeli: {model}", flush=True)
                return bool(j.get("ok")), int(j.get("siddet", 0)), str(j.get("sorun", ""))
            except urllib.error.HTTPError as e:
                print(f"::warning::Görsel kontrol ({model}) olmadı: HTTP {e.code}", flush=True)
                if e.code in (429, 500, 503):
                    time.sleep(15 * (deneme + 1))
                    continue
                break
            except (urllib.error.URLError, KeyError, IndexError, ValueError, TimeoutError) as e:
                print(f"::warning::Görsel kontrol ({model}) olmadı: {e}", flush=True)
                break
    return None

def main():
    import json
    ep_path, idx, sd, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
    ep = json.load(open(ep_path, encoding="utf-8"))
    if idx > len(ep["scenes"]):
        print(f"Bölümde {idx}. sahne yok, atlanıyor.")
        return
    os.makedirs(out, exist_ok=True)
    paths = {k: fetch(MODEL[k]) for k in ("diffusion", "llm", "vae")}
    dst = os.path.join(out, f"sahne{idx}.png")
    desc = ep["scenes"][idx - 1]["prompt"]
    for key, d in ep.get("characters", {}).items():
        desc = desc.replace("{" + key + "}", d)
    deneme = int(os.environ.get("CIZIM_DENEME", "3"))
    en_iyi = None                                   # (şiddet, yol)
    for n in range(deneme):
        seed = int(ep.get("seed", 100)) + idx + 1000 * n
        yol = dst if n == 0 else os.path.join(out, f"_sahne{idx}_{n}.png")
        t = time.time()
        cmd = [sd, "--diffusion-model", paths["diffusion"], "--llm", paths["llm"], "--vae", paths["vae"],
               "-p", build_prompt(ep, idx), "--cfg-scale", "1.0", "--steps", str(MODEL["steps"]),
               "--sampling-method", "euler", "-W", str(WIDTH), "-H", str(HEIGHT), "-s", str(seed),
               "-t", str(os.cpu_count() or 4), "-o", yol]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(yol):
            print(r.stdout[-3000:], r.stderr[-3000:])
            raise SystemExit(f"sahne {idx} çizilemedi")
        print(f"sahne {idx} (deneme {n + 1}, tohum {seed}): {time.time() - t:.0f} sn", flush=True)
        q = kalite(yol, desc)
        if q is None:
            en_iyi = (0, yol)
            break
        ok, siddet, sorun = q
        print(f"  görsel kontrol: {'temiz' if ok else 'HATA'} (şiddet {siddet}) {sorun}", flush=True)
        if en_iyi is None or siddet < en_iyi[0]:
            en_iyi = (siddet, yol)
        if ok and siddet <= 2:
            break
    if en_iyi[1] != dst:
        os.replace(en_iyi[1], dst)
    for f in os.listdir(out):
        if f.startswith(f"_sahne{idx}_"):
            os.remove(os.path.join(out, f))
    print(f"sahne {idx}: seçilen şiddet {en_iyi[0]}")

if __name__ == "__main__":
    main()
