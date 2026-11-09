# Kıssadan Hisse · @kissadan.hisse.tr

Halk anlatılarından (Nasreddin Hoca, Kelile ve Dimne, Mesnevi, Ezop, Lokman Hekim, Anadolu masalları) kısa kıssalar:
2D çizgi film tarzı yapay zekâ çizimleri, Gemini anlatıcı, sıcak masal müziği, sonda "kıssadan hisse" kartı. Her akşam 21:30.

- Format: `docs/senaryo_formati.md` · Kıssalar: `episodes/` · Paylaşım kaydı: `state/posted.json`
- **Hazırla**: sahneleri paralel çizer (Gemini ile hata kontrolü), sesi + müziği ekler, `hazir-<id>` sürümüne koyar.
- **Günlük paylaşım**: hazır olan sıradaki kıssayı paylaşır (yalnızca `assets/yayinda` varken). **Önizleme**: farklı seslerle deneme.
- Deneme reels: `publisher.publish_reel(..., trial="SS_PERFORMANCE")` (önce takipçi olmayanlara gösterilir).
- Secret'lar: `IG_ACCESS_TOKEN`, `GEMINI_API_KEY`. Paylaşım yalnızca `@kissadan.hisse.tr` hesabına yapılır.
