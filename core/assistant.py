import re
import time
from http.client import HTTPException

from core import config
from core.ai.gemini import GeminiClient
from core.ai.local_tasks import LocalTaskPlanner
from core.command_router import CommandRouter, NEGATION
from core.state import AssistantMode
from core.tasks import SOLO_COMMANDS, Step, is_question, local_plan
from core.text import normalize_text
from core.events import emit_event
from core.tts import speak, set_audio_guard, text_only


class Assistant:
    def __init__(self, stt, commands: dict):
        self.stt = stt
        self.router = CommandRouter(commands, config.CONFIDENCE_THRESHOLD)
        self.mode = AssistantMode.SYSTEM
        self.gemini = GeminiClient(config.GEMINI_API_KEY if config.AI_ENABLED else "")
        self.planner = LocalTaskPlanner(config.LOCAL_TASK_MODEL)
        self.cancelled = lambda: False
        self.session_active = False
        self.session_timeout = config.COMMAND_TIMEOUT
        self.last_activity = time.monotonic()
        self.fail_count = 0
        self.pending_action = None
        aliases = [config.WAKEWORD, *config.WAKEWORD_ALIASES]
        # Vosk can transcribe the Persian name as «سرویس». Include it for
        # existing installations whose user config overrides the bundled list.
        if normalize_text(config.WAKEWORD) == "جارویس":
            aliases.append("سرویس")
        self.wakewords = sorted({normalize_text(w) for w in aliases if w.strip()}, key=len, reverse=True)
        self.wake_pattern = r"^(?:" + "|".join(re.escape(w) for w in self.wakewords) + r")(?!\w)"
        if stt is not None:
            phrases = [variant for variants in commands for variant in variants]
            phrases += config.AI_ON_PHRASES + config.AI_OFF_PHRASES + ["تایید می کنم", "تایید میکنم", "بله انجام بده"]
            stt.set_command_phrases([*self.wakewords, *config.SEPARATORS, *phrases,
                                     *(f"{wake} {phrase}" for wake in self.wakewords for phrase in phrases)])
            stt.set_command_mode(True)
            set_audio_guard(stt.suspended)

    def speak(self, text):
        speak(text)
        self.last_activity = time.monotonic()

    def reset_session(self):
        self.session_active = False
        self.fail_count = 0
        self.pending_action = None

    def wakeword_detect(self, text: str) -> bool:
        return bool(re.search(self.wake_pattern, normalize_text(text)))

    def handle_fail(self, text, voice):
        emit_event("unrecognized", text=text, voice=voice)
        if not voice:
            return
        self.fail_count += 1
        if self.fail_count >= 5:
            self.reset_session()
            emit_event("notice", text="برای ادامه بگو «جارویس» یا دکمهٔ «بیدار شو» را بزن.")

    def handle_ai(self, text):
        if not self.gemini.available:
            self.speak("هوش مصنوعی در دسترس نیست. کلید جمینای را در تنظیمات وارد کن.")
            self.mode = AssistantMode.SYSTEM
            return
        self.speak("دارم فکر می کنم.")
        answer = self.gemini.ask(text)
        self.speak(answer or "پاسخی دریافت نشد. اینترنت و کلید هوش مصنوعی را بررسی کن.")

    def run_steps(self, steps):
        for index, step in enumerate(steps, 1):
            if self.cancelled():
                return
            emit_event("state", value="processing")
            emit_event("command", name=step.name, phrase=step.title, index=index, total=len(steps))
            try:
                response = step.action()
                if isinstance(response, str):
                    self.speak(response)
            except Exception as error:
                print("خطا در اجرای فرمان:", error)
                detail = str(error)
                if isinstance(error, FileExistsError):
                    detail = "فایلی با این نام از قبل وجود دارد."
                self.speak(f"«{step.title}» انجام نشد.\n{detail}")
                remaining = len(steps) - index
                if remaining:
                    self.speak(f"{remaining} مرحلهٔ بعدی اجرا نشد.")
                break
        self.last_activity = time.monotonic()

    def process_text(self, text, activated=False):
        # Only normalize spelling here; preserve the user's question for AI.
        normalized = normalize_text(text)
        if activated:
            self.session_active = True
            self.fail_count = 0
        if not self.session_active:
            if not self.wakeword_detect(normalized):
                return
            self.session_active = True
            self.fail_count = 0
            if not re.sub(self.wake_pattern, "", normalized).strip():
                emit_event("transcript", text=text)
                with text_only():
                    self.speak("گوش می کنم.")
                return
        normalized = re.sub(self.wake_pattern, "", normalized, count=1).strip()
        emit_event("transcript", text=text)
        self.last_activity = time.monotonic()
        emit_event("state", value="processing")
        if self.pending_action:
            action, expires = self.pending_action
            self.pending_action = None
            if time.monotonic() <= expires and normalized in ("تایید می کنم", "تایید میکنم", "بله انجام بده"):
                self.run_steps([Step("پاک‌سازی", action, action.__name__)])
            else:
                self.speak("پاکسازی لغو شد.")
            return
        if normalized in [normalize_text(p) for p in config.AI_OFF_PHRASES]:
            self.mode = AssistantMode.SYSTEM
            self.speak("به حالت دستورات برگشتم.")
            return
        if normalized in [normalize_text(p) for p in config.AI_ON_PHRASES]:
            if not config.AI_ENABLED:
                self.speak("هوش مصنوعی در تنظیمات غیرفعال است.")
            elif not self.gemini.available:
                self.speak("برای گفت و گو، کلید جمینای را در تنظیمات وارد کن.")
            else:
                self.mode = AssistantMode.AI
                self.speak("حالت گفت و گوی فارسی فعال شد.")
            return
        if self.mode == AssistantMode.AI:
            # Exit remains available; other requests are conversation, not actions.
            if normalized not in ("خداحافظ", "خارج شو", "برنامه را ببند", "برنامه رو ببند"):
                self.handle_ai(normalized)
                return
        request = re.sub(self.wake_pattern + r"[\s،,:؛]+", "", text.strip(), count=1, flags=re.IGNORECASE)
        try:
            steps = local_plan(request, self.router)
            if not steps and not activated and normalized != normalize_text(request):
                steps = local_plan(normalized, self.router)
        except ValueError as error:
            with text_only():
                self.speak(str(error))
            if not activated:
                emit_event("unrecognized", text=text, voice=True)
            return
        actionable = not NEGATION.search(normalized) and not is_question(request)
        if not steps and config.LOCAL_TASK_MODEL and actionable:
            emit_event("planning")
            try:
                steps = self.planner.plan(request)
            except (OSError, HTTPException, KeyError, TypeError, ValueError) as error:
                print("خطای برنامه‌ریزی محلی:", error)
        if not steps and not activated and actionable and len(self.router.split_phrases(normalized)) == 1:
            commands = self.router.detect(normalized)
            steps = [Step(phrase, action, action.__name__) for action, _, phrase in commands
                     if action.__name__ not in SOLO_COMMANDS]
        if not steps:
            self.handle_fail(text, voice=not activated)
            return
        self.fail_count = 0
        if steps[0].name == "clean_all_files":
            self.speak("این کار فایل های موقت و سطل زباله را پاک می کند. برای ادامه بگو تایید می کنم.")
            self.pending_action = (steps[0].action, time.monotonic() + self.session_timeout)
            return
        self.run_steps(steps)

    def run(self):
        if config.TTS_ENGINE == "edge":
            print("صدای آنلاین فارسی فعال است؛ متن پاسخ برای تولید صدا ارسال می شود.")
        self.speak("سلام. جارویس آماده است. برای شروع اسمم را صدا بزن.")
        while True:
            try:
                if self.session_active and time.monotonic() - self.last_activity > self.session_timeout:
                    self.reset_session()
                self.stt.set_command_mode(self.mode == AssistantMode.SYSTEM)
                text = self.stt.listen(timeout=12 if self.session_active else 2, silence_timeout=config.SILENCE_TIMEOUT)
                if text:
                    print("شما:", text)
                    self.process_text(text)
            except Exception as error:
                print("خطا در پردازش صدا:", error)
                time.sleep(.5)
