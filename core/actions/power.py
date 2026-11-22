import os
from core.tts import speak
import ctypes


def shutdown_pc():
    speak("خاموش کردن کامپیوتر در این نسخه فعال نیست.")
    # os.system("shutdown /s /t 5")


def cancel_shutdown():
    speak("لغو خاموش شدن در این نسخه فعال نیست.")
    # os.system("shutdown /a")


def restart_pc(*args, **kwargs):
    speak("راه اندازی مجدد کامپیوتر در این نسخه فعال نیست.")
    # os.system("shutdown /r /t 5")


def lock_pc(*args, **kwargs):
    speak("صفحه را قفل می کنم.")
    ctypes.windll.user32.LockWorkStation()
