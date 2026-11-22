import os
import platform
from core.tts import speak


def lock_screen():
    if platform.system() == "Windows":
        speak("صفحه را قفل می کنم.")
        os.system("rundll32.exe user32.dll,LockWorkStation")
