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

---

## 13 Kasım: İLK 3 SANİYE kuralları (ZORUNLU, diğer kurallarla çelişirse bu geçerli)

Veri: 8 kanalda izleyici ortalama 5-13 sn'de kaydırıyor. Instagram videoyu önce küçük bir test grubuna gösteriyor; izlenme süresi, sona kadar izlenme ve DM ile gönderilme iyi değilse yaymıyor. Reels izleyicisi ~1,4 sn'de karar veriyor ve izlemelerin yarısından fazlası ses kapalı başlıyor.

**Motor ne yapıyor (otomatik):** 0. saniyede ekranda büyük kanca yazısı (~3 sn) + ilk 0,8 sn hızlı zoom. Yazı bölümdeki `"kanca_yazi"` alanından gelir; yoksa açıklamanın (caption / instagram_caption) ilk satırından, o da uzunsa ilk cümlesinden. Bu yüzden:
- Her bölüme `"kanca_yazi"` ekle: en fazla 8 kelime, sessizken tek başına merak uyandıran cümle (cevabı vermeden). Seslendirilen ilk cümleyle aynı olmak zorunda değil ama aynı merakı açsın. (Son Mola'da bu alan sahne içindedir ve 2-3 kelimedir; orada mevcut kural geçerli.)
- Açıklamanın ilk satırı da kısa ve merak uyandıran olsun (yedek kanca yazısı olarak kullanılıyor).

**Kanca puanlama (yazdıktan sonra her bölüm için):** İlk seslendirilen cümleyi ve kanca_yazi'yi şu 5 türe göre 1-5 puanla, kendine sor: "Akışta kaydırırken 1,5 sn'de durur muydum?"
1. Ortak dert: izleyicinin yaşadığı ama dile getirmediği bir sıkıntı (Reels'te en güçlüsü)
2. Merak boşluğu: kapanması için izlemek gereken bir soru/boşluk
3. İddialı/ters köşe cümle: doğru ama şaşırtıcı, karşı çıkılası bir iddia
4. Kalıp kırma: beklenmedik bir giriş
5. Görsel şok: ilk karede açıklama isteyen bir görüntü
En yüksek puan 4'ün altındaysa ilk cümleyi yeniden yaz. Selamlama, giriş, "bugün size … anlatacağım", tarih/yer ile başlamak YASAK; en çarpıcı an ilk cümlede. Doğruluk kuralları aynen geçerli (abartı/uydurma yok).

**Gönderilme (DM) sebebi:** Instagram'da yeni kişilere ulaştıran en güçlü sinyal videonun DM ile birine gönderilmesi. Her bölümün SON seslendirilen cümlesi (ya da kapanış kartı alt yazısı), izleyicinin videoyu belirli birine göndermesi için doğal bir sebep versin; TEK cümle, dilenmeden: "Bunu her ay sonu batan arkadaşına gönder.", "Bunu gece yolculuğu seven birine gönder." Açıklamadaki tek çağrı kuralı aynen kalır (bu cümle videonun içinde).
