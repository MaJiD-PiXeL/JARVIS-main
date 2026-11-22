"""Persian speech output. Edge sends response text online; system is offline."""
import asyncio
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
import ctypes
from pathlib import Path
import sys
import tempfile
import uuid
import time

from core import config
from core.events import emit_event

_audio_guard = nullcontext
_system_engine = None
_system_unavailable = False
_muted = False
_stop_event = None
_text_only = ContextVar("text_only", default=False)


@contextmanager
def text_only():
    token = _text_only.set(True)
    try:
        yield
    finally:
        _text_only.reset(token)


def set_muted(value):
    global _muted
    _muted = bool(value)


def set_stop_event(event):
    global _stop_event
    _stop_event = event


def _stopping():
    return _stop_event is not None and _stop_event.is_set()


def set_audio_guard(guard):
    global _audio_guard
    _audio_guard = guard


def _play_mp3(path):
    if sys.platform != "win32":
        raise RuntimeError("پخش داخلی صدا فقط در ویندوز پشتیبانی می‌شود")
    alias = "jarvis_" + uuid.uuid4().hex
    send = ctypes.windll.winmm.mciSendStringW
    def command(value):
        error = send(value, None, 0, None)
        if error:
            raise RuntimeError(f"خطای پخش صدا: {error}")
    try:
        command(f'open "{path}" type mpegvideo alias {alias}')
        command(f"play {alias}")
        buffer = ctypes.create_unicode_buffer(64)
        while not _stopping():
            error = send(f"status {alias} mode", buffer, len(buffer), None)
            if error:
                raise RuntimeError(f"خطای پخش صدا: {error}")
            if buffer.value != "playing":
                break
            time.sleep(.05)
    finally:
        send(f"close {alias}", None, 0, None)


async def _edge_audio(text, path):
    import edge_tts
    task = asyncio.create_task(edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE).save(str(path)))
    deadline = time.monotonic() + 7
    try:
        while not task.done():
            if _stopping():
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("مهلت دریافت صدای آنلاین تمام شد")
            await asyncio.wait({task}, timeout=.1)
        await task
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


def _system_speak(text):
    global _system_engine, _system_unavailable
    if _system_unavailable:
        return
    if _system_engine is None:
        import pyttsx3
        engine = pyttsx3.init()
        voice = None
        for candidate in engine.getProperty("voices"):
            languages = " ".join(str(v).lower() for v in getattr(candidate, "languages", []))
            label = (candidate.id + " " + candidate.name).lower()
            if config.SYSTEM_VOICE_ID:
                matches = candidate.id == config.SYSTEM_VOICE_ID
            else:
                matches = any(v in languages for v in ("fa-ir", "fa_ir", "persian", "farsi")) or any(v in label for v in ("persian", "farsi"))
            if matches:
                voice = candidate
                break
        if voice is None:
            _system_unavailable = True
            engine.stop()
            raise RuntimeError("صدای فارسی آفلاین نصب نیست؛ پاسخ به صورت متن نمایش داده می‌شود")
        engine.setProperty("voice", voice.id)
        engine.setProperty("rate", 165)
        _system_engine = engine
    _system_engine.say(text)
    _system_engine.runAndWait()


def speak(text):
    if not text:
        return
    print(f"جارویس: {text}")
    emit_event("response", text=text)
    if _muted or _text_only.get() or _stopping():
        return
    emit_event("state", value="speaking")
    with _audio_guard():
        if config.TTS_ENGINE == "edge":
            try:
                with tempfile.TemporaryDirectory(prefix="jarvis_speech_") as folder:
                    path = Path(folder) / "speech.mp3"
                    asyncio.run(_edge_audio(text, path))
                    if _stopping():
                        return
                    _play_mp3(path)
                return
            except Exception as error:
                print("صدای آنلاین در دسترس نیست:", error)
                emit_event("notice", text="صدای آنلاین در دسترس نیست؛ خروجی آفلاین بررسی می‌شود.")
        try:
            _system_speak(text)
        except Exception as error:
            print("خروجی صوتی در دسترس نیست:", error)
            emit_event("notice", text=str(error))
