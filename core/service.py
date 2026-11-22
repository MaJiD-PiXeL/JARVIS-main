"""Serialize audio and commands on one worker; the GUI never blocks on speech."""
import ctypes
import queue
import sys
import threading
import time

from core import config
from core.events import emit_event
from core.state import AssistantMode
from core import tts


class AssistantService(threading.Thread):
    def __init__(self):
        super().__init__(name="Jarvis audio", daemon=True)
        self.controls = queue.Queue(maxsize=32)
        self.stopping = threading.Event()
        self.listening = False
        self.assistant = None
        self.stt = None
        self.testing = False
        self._listening_before_test = False

    def submit(self, kind, **data):
        if self.stopping.is_set():
            return False
        try:
            self.controls.put_nowait((kind, data))
            return True
        except queue.Full:
            return False

    def shutdown(self):
        self.stopping.set()

    def _state(self):
        emit_event("mode", value=self.assistant.mode)
        state = "testing" if self.testing else "paused" if not self.listening else "listening" if self.assistant.session_active else "waiting"
        emit_event("state", value=state)

    def _control(self, kind, data):
        if self.stt is None and kind != "text":
            return
        if kind == "test_microphone":
            if data["enabled"] and not self.testing:
                self._listening_before_test = self.listening
                self._input_before_test = (self.stt.device, self.stt.input_gain, self.stt.grammar_enabled)
                self.stt.configure_input(data["device"], data["gain"], data["grammar"])
                self.testing = True
                self.listening = True
            elif not data["enabled"] and self.testing:
                self.testing = False
                self.listening = self._listening_before_test
                self.stt.configure_input(*self._input_before_test)
            self.stt.stop()
            self.stt.discard_audio()
        elif kind == "listening":
            self.listening = data["enabled"]
            if not self.listening:
                self.stt.stop()
                self.stt.discard_audio()
                self.assistant.reset_session()
            else:
                self.assistant.session_active = True
                self.assistant.last_activity = time.monotonic()
        elif kind == "text":
            guard = self.stt.suspended if self.stt is not None and self.stt.active else tts.nullcontext
            with guard(), tts.text_only():
                self.assistant.process_text(data["text"], activated=True)
        elif kind == "activate":
            self.stt.discard_audio()
            self.listening = True
            self.assistant.session_active = True
            self.assistant.last_activity = time.monotonic()
        elif kind == "settings":
            self.stt.configure_input(data["device"], data["gain"], data["grammar"])
            config.save_audio_settings({"microphone_index": data["device"], "input_gain": data["gain"],
                                        "command_grammar": data["grammar"]})
            emit_event("settings_saved", device=data["device"], gain=data["gain"], grammar=data["grammar"])
            emit_event("notice", text="تنظیمات میکروفون ذخیره شد.")
        self._state()

    def run(self):
        com_ready = False
        try:
            if sys.platform == "win32":
                com_ready = ctypes.windll.ole32.CoInitialize(None) >= 0
            from core.assistant import Assistant
            from core.commands_loader import load_commands
            from core.tasks import EXAMPLES

            tts.set_stop_event(self.stopping)
            emit_event("state", value="loading")
            commands = load_commands()
            voice_error = None
            try:
                from core.stt import SpeachToText

                self.stt = SpeachToText(config.MODEL_PATH)
            except Exception as error:
                # A missing dependency or invalid model should only disable voice input.
                voice_error = str(error)
            self.assistant = Assistant(self.stt, commands)
            self.assistant.cancelled = self.stopping.is_set
            if self.stopping.is_set():
                return
            emit_event("ready", ai_available=self.assistant.gemini.available,
                       voice_available=self.stt is not None, command_groups=tuple(commands) + tuple((text,) for text in EXAMPLES))
            if self.stt is None:
                emit_event("notice", text=f"تشخیص گفتار در دسترس نیست. فرمانت را بنویس.\n{voice_error}")
            else:
                emit_event("response", text="سلام. من جارویس هستم؛ برای شروع، میکروفون را روشن کن یا فرمانت را بنویس.")
            self._state()
            while not self.stopping.is_set():
                try:
                    try:
                        kind, data = self.controls.get(timeout=.1 if not self.listening else .001)
                    except queue.Empty:
                        pass
                    else:
                        self._control(kind, data)
                    if self.stopping.is_set() or not self.listening:
                        continue
                    if (self.assistant.session_active and not self.stt.utterance_in_progress
                            and time.monotonic() - self.assistant.last_activity > self.assistant.session_timeout):
                        self.assistant.reset_session()
                    self.stt.set_command_mode(self.assistant.mode == AssistantMode.SYSTEM)
                    self._state()
                    text = self.stt.listen(timeout=.5, silence_timeout=config.SILENCE_TIMEOUT,
                                           interrupted=lambda: self.stopping.is_set() or not self.controls.empty())
                    if text and not self.stopping.is_set():
                        if self.testing:
                            emit_event("test_transcript", text=text)
                        else:
                            with self.stt.suspended():
                                self.assistant.process_text(text)
                        self._state()
                except Exception as error:
                    self.listening = False
                    if self.stt is not None:
                        self.stt.stop()
                        self.stt.discard_audio()
                    emit_event("error", text=str(error))
                    self._state()
        except SystemExit:
            self.stopping.set()
        except Exception as error:
            emit_event("error", text=str(error), fatal=True)
        finally:
            try:
                if self.stt is not None:
                    self.stt.stop()
                if self.assistant is not None:
                    client = self.assistant.gemini.genai_client
                    if client is not None:
                        client.close()
            except Exception as error:
                emit_event("notice", text=f"خطا هنگام آزادکردن منابع: {error}")
            finally:
                tts.set_audio_guard(tts.nullcontext)
                tts.set_stop_event(None)
                # Release native resources on their owner thread before COM
                # and the Qt application are torn down.
                self.assistant = None
                self.stt = None
                if com_ready:
                    ctypes.windll.ole32.CoUninitialize()
                emit_event("closed")
