import os
import random
from pathlib import Path
from core import config


def play_music(*args, **kwargs):
    try:
        music_dir = Path(config.MUSICS_DIR).expanduser() if config.MUSICS_DIR else Path.home() / "Music"
        if not music_dir.is_dir():
            return "پوشه موسیقی پیدا نشد. مسیر آن را در تنظیمات وارد کن."
        extensions = {".mp3", ".wav", ".flac", ".m4a", ".ogg"}
        songs = [p for p in music_dir.rglob("*") if p.is_file() and p.suffix.lower() in extensions]
        if not songs:
            return "آهنگی در پوشه موسیقی پیدا نکردم."
        song = random.choice(songs)
        os.startfile(song)
        return f"آهنگ {song.stem} را پخش می کنم."
    except Exception as error:
        print("خطا در پخش موسیقی:", error)
        return "پخش موسیقی با خطا روبه رو شد."
