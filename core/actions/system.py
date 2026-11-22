import os
import sys
import time
import ctypes
from core.tts import speak
import platform
import psutil


def exit_assistant(*args, **kwargs):
    speak("خداحافظ. جارویس بسته می شود.")
    time.sleep(0.5)
    sys.exit(0)


def get_system_info(*args, **kwargs):
    try:
        ram = round(psutil.virtual_memory().total / (1024**3), 1)
        cpu = platform.processor()

        text = f"سیستم عامل ویندوز. پردازنده {cpu}. حافظه رم {ram} گیگابایت."

        speak(text)

    except Exception as e:
        print("خطای دریافت مشخصات سیستم:", e)
        speak("دریافت مشخصات سیستم امکان پذیر نبود.")
