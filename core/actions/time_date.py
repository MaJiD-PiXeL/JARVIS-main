from datetime import datetime
import jdatetime
from core.tts import speak

MONTHS = ("فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند")
WEEKDAYS = ("دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه")


def say_time(*args, **kwargs):
    now = datetime.now()
    speak(f"الان ساعت {now.hour} و {now.minute} دقیقه است.")


def say_date(*args, **kwargs):
    today = jdatetime.date.today()
    weekday = WEEKDAYS[datetime.now().weekday()]
    speak(f"امروز {weekday}، {today.day} {MONTHS[today.month - 1]} {today.year} است.")
