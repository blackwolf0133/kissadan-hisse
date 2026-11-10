"""Pilot video birleştirme. Kullanım: python -m pilot_islami.video <bölüm.json> <resim_klasörü> <çıktı.mp4>"""
import sys

from pilot_islami import ayar  # noqa: F401  (başlık, son kart, müzik)
from engine import video

if __name__ == "__main__":
    video.render_episode(sys.argv[1], sys.argv[2], sys.argv[3])
