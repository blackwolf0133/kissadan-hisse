"""Instagram Reels paylaşımı (resmi Meta Graph API, ücretsiz).

İki bağlantı türü desteklenir (IG_MODE ortam değişkeni):
  instagram (varsayılan) : "Instagram ile giriş" - Facebook sayfası gerekmez.
                           Video herkese açık bir URL'den (GitHub Pages) alınır.
  facebook               : "Facebook ile giriş" - Instagram hesabına bağlı bir Facebook
                           sayfası gerekir. Video doğrudan dosyadan yüklenir (resumable).

Gerekli ortam değişkenleri (GitHub Secrets):
  IG_USER_ID       Instagram profesyonel hesap kimliği
  IG_ACCESS_TOKEN  Uzun ömürlü erişim anahtarı (60 gün; refresh_token() ile uzatılır)
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("IG_API_VERSION", "v26.0")


class PublishError(RuntimeError):
    pass


def detect_mode(token=None):
    """Anahtarın türüne göre bağlantı yolunu seç.
    IG ile başlayan anahtar -> Instagram girişi (graph.instagram.com)
    EAA ile başlayan anahtar -> Facebook girişi (graph.facebook.com)
    IG_MODE ortam değişkeni verilmişse o kullanılır."""
    m = os.environ.get("IG_MODE", "").strip().lower()
    if m in ("instagram", "facebook"):
        return m
    token = (token or os.environ.get("IG_ACCESS_TOKEN", "")).strip()
    return "facebook" if token.startswith("EAA") else "instagram"


def _host(mode):
    return "graph.instagram.com" if mode == "instagram" else "graph.facebook.com"


def _request(method, url, params=None, headers=None, data=None, timeout=120):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise PublishError(f"HTTP {e.code} {url.split('?')[0]}: {body}") from None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def wait_for_url(url, timeout=300):
    """GitHub Pages yayına alana kadar bekle."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(10)
    raise PublishError(f"Video adresi {timeout} sn içinde erişilebilir olmadı: {url}")


def _wait_container(host, container_id, token, timeout=900):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        info = _request("GET", f"https://{host}/{API_VERSION}/{container_id}",
                        {"fields": "status_code,status", "access_token": token})
        last = info
        code = info.get("status_code")
        if code == "FINISHED":
            return info
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram videoyu işleyemedi: {info}")
        time.sleep(10)
    raise PublishError(f"Video işleme zaman aşımı. Son durum: {last}")


HESAP = os.environ.get("IG_USERNAME", "kissadan.hisse.tr").strip().lstrip("@").lower()
VARSAYILAN_KIMLIK = os.environ.get("IG_KIMLIK", "17841422724352077")   # @kissadan.hisse.tr Instagram kimliği


def _kullanici_adi(uid, token, mode):
    r = _request("GET", f"https://{_host(mode)}/{API_VERSION}/{uid}", {"fields": "username", "access_token": token})
    return (r.get("username") or "").lower()


def resolve_user_id(token, mode):
    """Paylaşılacak Instagram hesabının kimliği. Aynı anahtar başka kanallara da erişebildiği için
    hesap HER ZAMAN kullanıcı adıyla (IG_USERNAME, varsayılan kissadan.hisse.tr) doğrulanır; eşleşmezse paylaşım yapılmaz."""
    uid = os.environ.get("IG_USER_ID", "").strip() or VARSAYILAN_KIMLIK
    if uid:
        ad = _kullanici_adi(uid, token, mode)
        if ad != HESAP:
            raise PublishError(f"IG_USER_ID başka bir hesaba ait (@{ad}), @{HESAP} değil. Paylaşım durduruldu.")
        return uid
    if mode != "instagram":
        g = f"https://graph.facebook.com/{API_VERSION}"
        adaylar = []
        try:
            r = _request("GET", f"{g}/me/accounts", {"fields": "instagram_business_account{id,username}",
                                                      "limit": 100, "access_token": token})
            adaylar += [it["instagram_business_account"] for it in r.get("data", []) if it.get("instagram_business_account")]
        except PublishError:
            pass
        try:
            biz = _request("GET", f"{g}/me/businesses", {"fields": "id", "access_token": token}).get("data", [])
        except PublishError:
            biz = []
        for b in biz:
            for kenar in ("owned_instagram_accounts", "instagram_business_accounts", "client_instagram_accounts"):
                try:
                    r = _request("GET", f"{g}/{b['id']}/{kenar}", {"fields": "id,username", "limit": 100,
                                                                  "access_token": token})
                    adaylar += r.get("data", [])
                except PublishError:
                    pass
        for h in adaylar:
            if (h.get("username") or "").lower() == HESAP:
                return h["id"]
        bulunan = ", ".join(sorted({"@" + (h.get("username") or "?") for h in adaylar})) or "hiçbiri"
        raise PublishError(f"@{HESAP} hesabı bu anahtarla bulunamadı (erişilen hesaplar: {bulunan}). "
                           "Hesabı sistem kullanıcısına atayın ya da IG_USER_ID secret'ını ekleyin.")
    me = _request("GET", f"https://graph.instagram.com/{API_VERSION}/me",
                  {"fields": "user_id,username", "access_token": token})
    if (me.get("username") or "").lower() != HESAP:
        raise PublishError(f"Anahtar @{me.get('username')} hesabına ait, @{HESAP} değil. Paylaşım durduruldu.")
    return str(me.get("user_id") or me["id"])


def publish_reel(video_path=None, video_url=None, caption="", mode=None,
                 user_id=None, token=None, share_to_feed=True, trial=None):
    """Reel paylaşır, {"media_id", "permalink"} döndürür."""
    token = token or os.environ["IG_ACCESS_TOKEN"]
    mode = mode or detect_mode(token)
    user_id = user_id or resolve_user_id(token, mode)
    host = _host(mode)
    base = f"https://{host}/{API_VERSION}"

    params = {"media_type": "REELS", "caption": caption,
              "share_to_feed": "true" if share_to_feed else "false", "access_token": token}
    if trial:  # Deneme reels: önce sadece takipçi olmayanlara gösterilir; iyi giderse herkese açılır
        params["trial_params"] = json.dumps({"graduation_strategy": trial})

    upload_error = None
    if mode == "facebook":
        # 1) Yükleme oturumu aç
        params["upload_type"] = "resumable"
        c = _request("POST", f"{base}/{user_id}/media", params)
        cid = c["id"]
        upload_uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}/{cid}"
        uploaded = False
        # 2a) Meta videoyu herkese açık adresten kendisi çeksin (~40 sn üstü Reels için güvenilir yol)
        if video_url:
            try:
                _request("POST", upload_uri, headers={"Authorization": f"OAuth {token}", "file_url": video_url},
                         timeout=600)
                uploaded = True
            except PublishError as e:
                upload_error = e
                print(f"file_url ile yükleme olmadı, dosyadan deneniyor: {e}")
        # 2b) Yedek: dosyayı doğrudan gönder
        if not uploaded and video_path and os.path.exists(video_path):
            size = os.path.getsize(video_path)
            with open(video_path, "rb") as fh:
                data = fh.read()
            try:
                _request("POST", upload_uri, headers={
                    "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
                    "Content-Type": "application/octet-stream"}, data=data, timeout=600)
                uploaded = True
            except PublishError as e:
                # Meta bazen hata döndürüp yine de işliyor; kararı kapsayıcı durumu versin
                upload_error = e
                print(f"Dosya yüklemesi hata verdi, kapsayıcı durumu kontrol ediliyor: {e}")
        if not uploaded and upload_error is None:
            raise PublishError("Yüklenecek video yok (ne video_url ne dosya)")
    else:
        if not video_url:
            raise PublishError("instagram modunda herkese açık video_url gerekir")
        wait_for_url(video_url)
        params["video_url"] = video_url
        c = _request("POST", f"{base}/{user_id}/media", params)
        cid = c["id"]

    # 3) Instagram işlemesini bitirsin
    try:
        _wait_container(host, cid, token, timeout=300 if upload_error else 900)
    except PublishError as e:
        if upload_error:
            raise PublishError(f"{e} | yükleme hatası: {upload_error}") from None
        raise
    # 4) Yayınla
    pub = _request("POST", f"{base}/{user_id}/media_publish", {"creation_id": cid, "access_token": token})
    media_id = pub["id"]
    link = None
    try:
        link = _request("GET", f"{base}/{media_id}", {"fields": "permalink", "access_token": token}).get("permalink")
    except PublishError:
        pass
    return {"media_id": media_id, "permalink": link, "container_id": cid}


# ---------------------------------------------------------------------------
# Hikâye (Story): Reel paylaşıldıktan sonra aynı video hikâyeye de konur (13 Kasım).
# API sınırı: video hikâye 3-60 sn; daha uzunsa ilk 59 sn kesilip dosyadan yüklenir.
# Bu adım ASLA paylaşımı bozmamalı: çağıran taraf hataları yakalar.

def _sure(path):
    import subprocess
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", path], capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return None


def _kirp(path, saniye=59):
    import subprocess
    hedef = os.path.splitext(path)[0] + "_hikaye.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-t", str(saniye),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", hedef],
                   check=True, timeout=600)
    return hedef


def publish_story(video_path=None, video_url=None, mode=None, user_id=None, token=None):
    """Videoyu hikâye olarak paylaşır, {"media_id"} döndürür."""
    token = token or os.environ["IG_ACCESS_TOKEN"]
    mode = mode or detect_mode(token)
    user_id = user_id or resolve_user_id(token, mode)
    host = _host(mode)
    base = f"https://{host}/{API_VERSION}"

    yerel = video_path if (video_path and os.path.exists(video_path)) else None
    sure = _sure(yerel) if yerel else None
    if sure is not None and sure > 60:
        if mode != "facebook":
            raise PublishError(f"Video {sure:.0f} sn (hikâye en fazla 60 sn) ve bu modda kırpılmış dosya yüklenemiyor")
        yerel = _kirp(yerel)
        video_url = None          # kırpılmış dosya doğrudan yüklenir
        print(f"Hikâye için video {sure:.0f} sn'den 59 sn'ye kırpıldı.")

    params = {"media_type": "STORIES", "access_token": token}
    if mode == "facebook":
        params["upload_type"] = "resumable"
        c = _request("POST", f"{base}/{user_id}/media", params)
        cid = c["id"]
        uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}/{cid}"
        ok = False
        if video_url:
            try:
                _request("POST", uri, headers={"Authorization": f"OAuth {token}", "file_url": video_url}, timeout=600)
                ok = True
            except PublishError as e:
                print(f"Hikâye: file_url olmadı, dosyadan deneniyor: {e}")
        if not ok:
            if not yerel:
                raise PublishError("Hikâye için yüklenecek dosya yok")
            with open(yerel, "rb") as fh:
                data = fh.read()
            try:
                _request("POST", uri, headers={"Authorization": f"OAuth {token}", "offset": "0",
                                               "file_size": str(len(data)),
                                               "Content-Type": "application/octet-stream"}, data=data, timeout=600)
            except PublishError as e:
                print(f"Hikâye: dosya yüklemesi hata verdi, kapsayıcı kontrol ediliyor: {e}")
    else:
        if not video_url:
            raise PublishError("instagram modunda hikâye için video_url gerekir")
        params["video_url"] = video_url
        cid = _request("POST", f"{base}/{user_id}/media", params)["id"]

    _wait_container(host, cid, token, timeout=420)
    pub = _request("POST", f"{base}/{user_id}/media_publish", {"creation_id": cid, "access_token": token})
    return {"media_id": pub["id"]}


def refresh_token(token=None):
    """Instagram ile giriş tokenının süresini 60 gün uzatır. Yeni tokenı döndürür."""
    token = token or os.environ["IG_ACCESS_TOKEN"]
    r = _request("GET", "https://graph.instagram.com/refresh_access_token",
                 {"grant_type": "ig_refresh_token", "access_token": token})
    return r.get("access_token"), r.get("expires_in")


def check_account(mode=None):
    """Bağlantıyı test eder: hesap adı ve kalan paylaşım hakkı."""
    token = os.environ["IG_ACCESS_TOKEN"]
    mode = mode or detect_mode(token)
    host = _host(mode)
    uid = resolve_user_id(token, mode)
    me = _request("GET", f"https://{host}/{API_VERSION}/{uid}", {"fields": "username", "access_token": token})
    lim = _request("GET", f"https://{host}/{API_VERSION}/{uid}/content_publishing_limit",
                   {"fields": "quota_usage,config", "access_token": token})
    return me, lim
