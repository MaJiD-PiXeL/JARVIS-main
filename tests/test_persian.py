"""Regression tests; no microphone, speech playback, or system actions are used."""

from contextlib import nullcontext
import atexit
import os
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

# Keep first-run config creation inside the workspace, not the user's AppData.
_settings = tempfile.TemporaryDirectory(prefix="jarvis_tests_", dir=Path(__file__).resolve().parent)
atexit.register(_settings.cleanup)
os.environ["JARVIS_CONFIG_DIR"] = _settings.name

import numpy as np
import yaml

from core import config
from core.assistant import Assistant
from core.command_router import CommandRouter
from core.text import normalize_text
from core import tts

ROOT = Path(__file__).resolve().parent.parent


def action_named(name):
    def action():
        pass
    action.__name__ = name
    return action


class PersianCommands(unittest.TestCase):
    def setUp(self):
        self.data = yaml.safe_load((ROOT / "commands.yaml").read_text(encoding="utf-8"))
        self.actions = {name: action_named(name) for name in self.data}
        commands = {tuple(settings["phrases"]): self.actions[name] for name, settings in self.data.items()}
        self.router = CommandRouter(commands, 85)

    def test_every_bundled_phrase_selects_its_action(self):
        for name, settings in self.data.items():
            for phrase in settings["phrases"]:
                with self.subTest(phrase=phrase):
                    result = self.router.detect(phrase)
                    self.assertEqual([a for a, _, _ in result], [self.actions[name]])

    def test_unicode_variants(self):
        self.assertEqual(normalize_text("لُطفاً كليد ۵۰ و ٥٠"), "لطفا کلید 50 و 50")
        result = self.router.detect("لطفاً ماشين‌حساب رو باز كن")
        self.assertEqual(result[0][0], self.actions["open_calculator"])

    def test_conjunction_does_not_break_words(self):
        text = "دوربین رو باز کن و بعد ماشین حساب رو باز کن"
        self.assertEqual(self.router.split_phrases(text), ["دوربین رو باز کن", "ماشین حساب رو باز کن"])
        self.assertEqual([a for a, _, _ in self.router.detect(text)], [self.actions["open_camera"], self.actions["open_calculator"]])

    def test_negative_and_unrelated_requests_do_not_execute(self):
        for phrase in ("صدا را قطع نکن", "مرورگر را باز نکن", "خارج نشو", "نمی خواهم خارج شو", "امروز چرا آسمان آبی است", "من موسیقی دوست دارم"):
            with self.subTest(phrase=phrase):
                self.assertEqual(self.router.detect(phrase), [])

    def test_scores_bounded_and_duplicates_removed(self):
        result = self.router.detect("گوگل رو باز کن و گوگل را باز کن")
        self.assertEqual(len(result), 1)
        self.assertTrue(0 <= result[0][1] <= 100)


class PersianAssistant(unittest.TestCase):
    def setUp(self):
        self.spoken = []
        self.speech = patch("core.assistant.speak", side_effect=self.spoken.append)
        self.speech.start()
        self.addCleanup(self.speech.stop)
        self.key = patch.object(config, "GEMINI_API_KEY", "")
        self.key.start()
        self.addCleanup(self.key.stop)
        self.open_browser = Mock(__name__="open_browser")
        self.cleaner = Mock(__name__="clean_all_files")
        self.assistant = Assistant(Mock(suspended=nullcontext), {
            ("مرورگر رو باز کن",): self.open_browser,
            ("سیستم را پاکسازی کن",): self.cleaner,
        })

    def test_waits_for_wake_word(self):
        self.assistant.process_text("مرورگر رو باز کن")
        self.open_browser.assert_not_called()
        self.assistant.process_text("جار ویس مرورگر رو باز کن")
        self.open_browser.assert_called_once()

    def test_wakeword_boundaries(self):
        self.assertFalse(self.assistant.wakeword_detect("جارویستان"))
        self.assertTrue(self.assistant.wakeword_detect("جارویس"))

    def test_vosk_wakeword_with_existing_user_aliases(self):
        # Existing user config need not contain the new recognition alias.
        say_time = Mock(__name__="say_time")
        with patch.object(config, "WAKEWORD_ALIASES", ["جارویس", "جار ویس"]):
            assistant = Assistant(Mock(suspended=nullcontext), {
                ("ساعت چنده",): say_time,
            })
        assistant.process_text("سرویس")
        self.assertTrue(assistant.session_active)
        self.assertEqual(self.spoken, ["گوش می کنم."])
        assistant.process_text("سی")
        assistant.process_text("ساعت چنده")
        say_time.assert_called_once()

    def test_vosk_wakeword_and_command_in_same_utterance(self):
        self.assistant.process_text("سرویس مرورگر رو باز کن")
        self.open_browser.assert_called_once()

    def test_vosk_alias_requires_whole_word(self):
        self.assertFalse(self.assistant.wakeword_detect("سرویسکار"))
        self.assertFalse(self.assistant.wakeword_detect("سی"))

    def test_custom_wakeword_does_not_use_jarvis_fallback(self):
        with patch.object(config, "WAKEWORD", "دستیار"), patch.object(config, "WAKEWORD_ALIASES", []):
            assistant = Assistant(Mock(suspended=nullcontext), {})
        self.assertFalse(assistant.wakeword_detect("سرویس"))

    def test_ai_switches_in_persian(self):
        self.assistant.gemini.available = True
        self.assistant.gemini.ask = Mock(return_value="سلام، چطور می توانم کمک کنم؟")
        self.assistant.process_text("جارویس حالت گفتگو")
        self.assistant.process_text("سلام")
        self.assistant.gemini.ask.assert_called_once_with("سلام")
        self.assistant.process_text("حالت عادی")
        self.assistant.process_text("مرورگر رو باز کن")
        self.open_browser.assert_called_once()

    def test_cleanup_needs_exact_confirmation(self):
        self.assistant.process_text("جارویس سیستم را پاکسازی کن")
        self.cleaner.assert_not_called()
        self.assistant.process_text("تایید نمی کنم")
        self.cleaner.assert_not_called()
        self.assistant.process_text("سیستم را پاکسازی کن")
        self.assistant.process_text("تأیید می‌کنم")
        self.cleaner.assert_called_once()

    def test_expired_cleanup_confirmation(self):
        self.assistant.session_active = True
        self.assistant.pending_action = (self.cleaner, -1)
        self.assistant.process_text("تایید می کنم")
        self.cleaner.assert_not_called()


class PersianAudio(unittest.TestCase):
    def test_pcm_rms_uses_signed_samples(self):
        from core.stt import SpeachToText
        stt = SpeachToText.__new__(SpeachToText)
        stt.queue = queue.Queue(maxsize=1)
        stt.noise_floor = 40
        samples = np.array([1000, -1000] * 800, dtype=np.int16)
        stt._callback(samples.tobytes(), len(samples), None, None)
        data, rms = stt.queue.get_nowait()
        self.assertEqual(data, samples.tobytes())
        self.assertAlmostEqual(rms, 1000)

    def test_tts_uses_persian_voice_and_audio_guard(self):
        guard = Mock(return_value=nullcontext())
        async def synthesize(text, path):
            self.assertEqual(text, "سلام")
            path.write_bytes(b"mock audio")
        with patch.object(tts, "_audio_guard", guard), patch.object(tts, "_edge_audio", synthesize), patch.object(tts, "_play_mp3") as play, patch.object(config, "TTS_ENGINE", "edge"):
            tts.speak("سلام")
            guard.assert_called_once()
            play.assert_called_once()

    def test_network_failure_falls_back_without_raising(self):
        async def fail(*args):
            raise ConnectionError("offline")
        with patch.object(tts, "_audio_guard", nullcontext), patch.object(tts, "_edge_audio", fail), patch.object(tts, "_system_speak") as fallback:
            tts.speak("سلام")
            fallback.assert_called_once_with("سلام")

    def test_resource_path_independent_of_working_directory(self):
        from core.stt import resource_path
        self.assertEqual(resource_path("models/small/vosk-fa"), config.RESOURCE_DIR / "models/small/vosk-fa")


if __name__ == "__main__":
    unittest.main()
