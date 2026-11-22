import time
from core import config

VOICE_SYSTEM_PROMPT = """تو جارویس، دستیار صوتی فارسی زبان هستی.
همیشه به فارسی روان، طبیعی و دوستانه پاسخ بده؛ مگر کاربر صریحا زبان دیگری بخواهد.
پاسخ باید برای شنیدن مناسب باشد: حداکثر دو یا سه جمله کوتاه، بدون مارک داون، فهرست، شکلک یا کد.
پرسش کاربر را تکرار نکن. اگر مطمئن نیستی صادقانه بگو.
تو فقط گفت و گو می کنی و به ابزارهای سیستم دسترسی نداری؛ ادعای اجرای فرمان نکن.
"""


class GeminiClient:
    def __init__(self, api_key):
        self.available = bool(api_key)
        self.max_chars = 600
        self.retry_count = 2
        self.genai_client = None
        if self.available:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=api_key)
            except Exception as error:
                print("خطا در راه اندازی جمینای:", error)
                self.available = False

    def ask(self, prompt):
        if not self.available:
            return None
        for attempt in range(self.retry_count):
            try:
                response = self.genai_client.models.generate_content(
                    model=config.AI_MODEL,
                    contents=prompt,
                    config={"system_instruction": VOICE_SYSTEM_PROMPT},
                )
                text = (getattr(response, "text", None) or "").strip()
                if not text:
                    return None
                return text if len(text) <= self.max_chars else text[:self.max_chars].rsplit(" ", 1)[0] + "…"
            except Exception as error:
                print(f"خطای ارتباط با جمینای، تلاش {attempt + 1}:", error)
                if attempt + 1 < self.retry_count:
                    time.sleep(1)
        return None
