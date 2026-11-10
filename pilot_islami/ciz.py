"""Pilot sahne çizimi (yüzsüz, sinematik stil). Kullanım: python -m pilot_islami.ciz <bölüm.json> <sahne_no> <sd-cli> <çıktı>"""
from pilot_islami import ayar  # noqa: F401  (stili değiştirir)
from engine import scenes

if __name__ == "__main__":
    scenes.main()
