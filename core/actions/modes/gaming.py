import os
import subprocess
from core.tts import speak
from .base import BaseMode



class GamingMode(BaseMode):

    name = "gaming"

    def __init__(self):
        self.prev_power_plan = None

    def enable(self):
        speak("در حال فعال کردن حالت بازی هستم.")

        self.save_current_power_plan()
        self.enable_high_performance()
        self.disable_notifications()
        self.kill_background_apps()

        speak("حالت بازی فعال شد.")

    