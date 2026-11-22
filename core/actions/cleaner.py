import shutil
import ctypes
from pathlib import Path
import tempfile
from core.tts import speak


def clear_temp_folder(*args, **kwargs):
    temp_path = Path(tempfile.gettempdir())

    for item in temp_path.iterdir():
        try:
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print("خطا در پاکسازی فایل موقت: ", e)


def clear_recycle_bin(*args, **kwargs):
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
    except Exception as e:
        print("خطا در خالی کردن سطل زباله: ", e)


def clean_all_files(*args, **kwargs):
    speak("در حال پاکسازی فایل های موقت و سطل زباله هستم.")
    clear_temp_folder()
    clear_recycle_bin()
    speak("عملیات پاکسازی پایان یافت. جزئیات خطاهای احتمالی در پنجره برنامه نمایش داده شده است.")
