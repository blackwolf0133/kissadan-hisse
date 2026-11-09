"""Türkçe sayı -> yazı (tarihler için)."""
import re

BIR = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
ON = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def sayi_yaz(n):
    if n == 0:
        return "sıfır"
    parts = []
    if n >= 1000:
        k = n // 1000
        parts.append("bin" if k == 1 else sayi_yaz(k) + " bin")
        n %= 1000
    if n >= 100:
        h = n // 100
        parts.append("yüz" if h == 1 else BIR[h] + " yüz")
        n %= 100
    if n >= 10:
        parts.append(ON[n // 10])
        n %= 10
    if n:
        parts.append(BIR[n])
    return " ".join(parts)


NUM_RE = re.compile(r"(\d+)(?:['’]([a-zA-ZçğıöşüÇĞİÖŞÜ]+))?")


def _sayilari_yaz(text):
    def rep(m):
        w = sayi_yaz(int(m.group(1)))
        return w + (m.group(2) or "")
    return NUM_RE.sub(rep, text)


YEAR_RE = re.compile(r"((?:[^\s.!?,:;]+\s+){0,2})(\d{3,4})(?:['’]([a-zA-ZçğıöşüÇĞİÖŞÜ]+))?")


def segmentler(text):
    """Metni (parça, yavaş_mı) listesine böler.
    Yıllar (3-4 haneli) ve önündeki en fazla 2 kelime tane tane okunur;
    diğer sayılar yazıya çevrilip normal akışta kalır."""
    out, pos = [], 0
    for m in YEAR_RE.finditer(text):
        if m.start() > pos:
            out.append((_sayilari_yaz(text[pos:m.start()]), False))
        phrase = _sayilari_yaz(m.group(1)) + sayi_yaz(int(m.group(2))) + (m.group(3) or "")
        out.append((phrase, True))
        pos = m.end()
    if pos < len(text):
        out.append((_sayilari_yaz(text[pos:]), False))
    res = []
    for t, sl in out:
        lead = t.lstrip()[:1] in ".!?"
        t = t.strip().lstrip(".,:;!? ")
        if t:
            res.append((t, sl, lead))
    return res


# --- Tüm ses motorları için okunuş düzeltmesi -------------------------------
# Klon ses modelleri (Chatterbox, Pocket) rakam, Roma rakamı ve sıra sayısı okuyamaz;
# metin modele gitmeden önce burada yazıya çevrilir.

_SIRA = {"bir": "birinci", "iki": "ikinci", "üç": "üçüncü", "dört": "dördüncü", "beş": "beşinci",
         "altı": "altıncı", "yedi": "yedinci", "sekiz": "sekizinci", "dokuz": "dokuzuncu",
         "on": "onuncu", "yirmi": "yirminci", "otuz": "otuzuncu", "kırk": "kırkıncı", "elli": "ellinci",
         "altmış": "altmışıncı", "yetmiş": "yetmişinci", "seksen": "sekseninci", "doksan": "doksanıncı",
         "yüz": "yüzüncü", "bin": "bininci"}
_ROMA = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def sira_yaz(n):
    """21 -> 'yirmi birinci'"""
    w = sayi_yaz(n).split()
    w[-1] = _SIRA[w[-1]]
    return " ".join(w)


def _roma(s):
    t = 0
    for i, c in enumerate(s):
        v = _ROMA[c]
        t += -v if i + 1 < len(s) and _ROMA[s[i + 1]] > v else v
    return t


_BUYUK = "A-ZÇĞİÖŞÜ"
ROMA_RE = re.compile(rf"\b([IVX]{{1,5}})\.\s+(?=[{_BUYUK}])")            # IV. Murad (M./C. gibi baş harfler hariç)
SIRA_RE = re.compile(r"\b(\d{1,4})\.\s+(?=[a-zçğıöşü])")                  # 19. yüzyıl
ONDALIK_RE = re.compile(r"\b(\d+),(\d+)\b")                               # 1,69
YUZDE_RE = re.compile(r"%\s?(\d+)")                                       # %20
BINLIK_RE = re.compile(r"\b(\d{1,3}(?:\.\d{3})+)\b(?!,\d)")               # 36.500


def _buyuk_bas(w):
    return ("İ" if w[0] == "i" else w[0].upper()) + w[1:]


def seslendirme_metni(text):
    """Metni ses modeline gitmeden önce okunur hale getirir."""
    text = ROMA_RE.sub(lambda m: _buyuk_bas(sira_yaz(_roma(m.group(1)))) + " ", text)
    text = SIRA_RE.sub(lambda m: sira_yaz(int(m.group(1))) + " ", text)
    text = YUZDE_RE.sub(lambda m: "yüzde " + m.group(1), text)
    text = BINLIK_RE.sub(lambda m: m.group(1).replace(".", ""), text)
    text = ONDALIK_RE.sub(lambda m: f"{sayi_yaz(int(m.group(1)))} virgül {sayi_yaz(int(m.group(2)))}", text)
    return _sayilari_yaz(text)


if __name__ == "__main__":
    for t in ["Yıl 1453. 21 yaşındaki Fatih", "29 Mayıs 1453'te İstanbul", "70 kadar gemi", "1071'de Malazgirt"]:
        print(segmentler(t))
