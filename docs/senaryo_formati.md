# Kıssadan Hisse · kıssa formatı

`episodes/NNN_kisa_ad.json`. Video 25-45 sn: 6-7 sahne, her sahnede 1-2 kısa cümle (toplam 70-95 kelime).

```json
{
  "id": "004", "slug": "kisa_ad", "title": "Kısa Başlık", "seed": 444,
  "characters": {"HOCA": "an old Turkish man with ... (İngilizce, ayırt edici tarif)"},
  "scenes": [
    {"text": "Türkçe cümle(ler)", "prompt": "English scene with {HOCA}", "yer": "Kaynak (yalnızca 1. sahnede)"}
  ],
  "hisse": "Sondaki kartta görünen tek cümlelik ders",
  "caption": "2-5 kelimelik merak sorusu + emoji\n\nHer akşam yeni bir kıssa için takip et 📜",
  "hashtags": ["#konu", "#kaynak", "#kıssadanhisse", "#...", "#kıssadanhissetr"]
}
```

## Yazım kuralları
- Kaynaklar halk anlatıları ve klasikler (Nasreddin Hoca, Kelile ve Dimne, Mesnevi, Ezop, Lokman Hekim, Kabusname, Anadolu
  masalları, padişah-derviş kıssaları). Her zaman KENDİ cümlelerimizle anlat; başka sayfaların videolarını/metinlerini kopyalama,
  başka kanalların anlattığı kıssaları aynı sırayla tekrar etme.
- 1. sahne kanca: sonucu ima eden çarpıcı/tezat bir cümle ("Aynı adam, aynı düğün. Ama ikinci gelişinde…", "…tek bir kelime yüzünden…").
- Ortada ters köşe; son sahne dersi tek cümlede söyler (hisse ile aynı ya da çok yakın). Din/siyaset tartışması yok, kimseyi aşağılama yok.
- Rakam yazılabilir (sesli okumada yazıya çevrilir). Diyalog tırnaksız, akıcı anlatım içinde.

## Çizim kuralları (stil otomatik: düz 2D çizgi film, kalın çizgi, sıcak toprak renkleri)
- Karakterleri `characters` içinde ayırt edici tarif et, sahnelerde {AD} ile kullan; sahnede en fazla 2-3 ana karakter.
- Tek net eylem; yazı/tabela isteme; şiddet ve yara gösterme (düşme vb. ima edilir).

## Haftalık trend raporu (last30days)
Her pazartesi blackwolf0133/cop-adamla-tarih deposundaki "Trend araştırma" iş akışı son 30 günün trendlerini 6 kanal için tarar
(YouTube, Reddit vb.; SCRAPECREATORS anahtarı varsa Instagram ve TikTok da). Yeni bölüm yazmadan önce en yeni raporu oku:

```bash
TAG=$(gh api "repos/blackwolf0133/cop-adamla-tarih/releases?per_page=20" --jq '[.[]|select(.tag_name|startswith("trend-"))][0].tag_name')
ID=$(gh api "repos/blackwolf0133/cop-adamla-tarih/releases/tags/$TAG" --jq '.assets[]|select(.name=="kissa.md").id')
gh api -H "Accept: application/octet-stream" "repos/blackwolf0133/cop-adamla-tarih/releases/assets/$ID" > /tmp/trend.md
```
Bu kanalın dosyası: **kissa.md**. Rapordaki tutan kanca kalıplarını, konu açılarını ve formatları kendi kurallarımıza uyarlayarak kullan;
başka içerik üreticilerinin metnini, videosunu ya da hikâyesini kopyalama. Rapor yoksa ya da eskiyse (14 günden eski) bu adımı atla.
