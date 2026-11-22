"""Recognition and worker regressions, without recording or executing actions."""
import json
import os
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("JARVIS_CONFIG_DIR", str(Path(__file__).resolve().parent.parent / ".test-config"))

from core import config
from core.stt import SpeachToText
from core.service import AssistantService


class RecognitionTests(unittest.TestCase):
    def make_stt(self):
        stt = SpeachToText.__new__(SpeachToText)
        stt.recognizer = Mock()
        stt.recognizer.AcceptWaveform.return_value = False
        stt.recognizer.PartialResult.return_value = '{"partial": "ساعت"}'
        stt.recognizer.FinalResult.return_value = '{"text": "ساعت چنده"}'
        stt.queue = queue.Queue()
        stt.noise_floor = 40.0
        stt._last_voice = None
        stt._utterance_start = None
        stt._partial = ""
        stt._segments = []
        stt._open_segments = []
        stt.start = Mock()
        return stt

    def test_command_vocabulary_preserves_negation_and_filters_unknown_words(self):
        stt = self.make_stt()
        stt.model = Mock()
        stt.model.vosk_model_find_word.side_effect = lambda word: -1 if word == "ناشناخته" else 1
        stt.set_command_phrases(["مرورگر رو باز کن", "ناشناخته رو باز کن"])
        self.assertIn("مرورگر رو باز نکن", stt._command_phrases)
        self.assertIn("تایید نمی کنم", stt._command_phrases)
        self.assertNotIn("ناشناخته رو باز کن", stt._command_phrases)

    def test_low_confidence_or_unknown_speech_never_becomes_a_command(self):
        stt = self.make_stt()
        for payload in ({"text": "مرورگر باز کن", "result": [{"conf": .2}]}, {"text": "[unk] مرورگر باز کن"}):
            with self.subTest(payload=payload), patch("core.stt.emit_event") as event:
                self.assertIsNone(stt._result(json.dumps(payload)))
                self.assertIn("uncertain", [call.args[0] for call in event.call_args_list])

    def test_clear_speech_returns_transcript_and_confidence(self):
        stt = self.make_stt()
        payload = {"text": "ساعت چنده", "result": [{"conf": .9}, {"conf": .8}]}
        with patch("core.stt.emit_event") as event:
            self.assertEqual(stt._result(json.dumps(payload)), "ساعت چنده")
            event.assert_any_call("confidence", value=.8500000000000001)

    def test_silence_detection_survives_short_listening_windows(self):
        stt = self.make_stt()
        stt.queue.put((b"voice", 1000))
        self.assertIsNone(stt.listen(timeout=.01, silence_timeout=.02))
        self.assertIsNotNone(stt._last_voice)
        time.sleep(.025)
        stt.queue.put((b"silence", 0))
        self.assertEqual(stt.listen(timeout=.1, silence_timeout=.02), "ساعت چنده")

    def test_pause_interrupts_listening_without_waiting_for_utterance_timeout(self):
        stt = self.make_stt()
        self.assertIsNone(stt.listen(timeout=12, interrupted=lambda: True))
        stt.recognizer.AcceptWaveform.assert_not_called()

    def test_internal_endpoint_preserves_both_parts_until_configured_silence(self):
        stt = self.make_stt()
        stt.recognizer.AcceptWaveform.side_effect = [True, False, False]
        stt.recognizer.Result.return_value = json.dumps({"text": "مرورگر رو باز کن"})
        stt.recognizer.FinalResult.return_value = json.dumps({"text": "و بعد ساعت چنده"})
        stt.queue.put((b"first", 1000))
        self.assertIsNone(stt.listen(timeout=.01, silence_timeout=.03))
        stt.queue.put((b"second", 1000))
        self.assertIsNone(stt.listen(timeout=.01, silence_timeout=.03))
        time.sleep(.035)
        stt.queue.put((b"silence", 0))
        self.assertEqual(stt.listen(timeout=.1, silence_timeout=.03), "مرورگر رو باز کن و بعد ساعت چنده")

    def test_free_transcript_preserves_words_missing_from_the_command_grammar(self):
        stt = self.make_stt()
        limited = json.dumps({"text": "[unk] رو باز کن"})
        free = json.dumps({"text": "باز کن نوت پد و ماشین حساب", "result": [{"conf": .9}]})
        self.assertEqual(stt._result(limited, free), "باز کن نوت پد و ماشین حساب")

    def test_grammar_fallback_needs_agreement_and_never_overrides_negation(self):
        stt = self.make_stt()
        limited = json.dumps({"text": "ماشین حساب رو باز کن", "result": [{"conf": .95}]})
        def weak(text):
            return json.dumps({"text": text, "result": [{"conf": .4}]})
        self.assertEqual(stt._result(limited, weak("ماشین حساب باز")), "ماشین حساب رو باز کن")
        self.assertIsNone(stt._result(limited, weak("نوت پد رو باز کن")))
        self.assertIsNone(stt._result(limited, weak("ماشین حساب رو باز نکن")))

    def test_switching_to_conversation_restores_unrestricted_recognizer(self):
        stt = self.make_stt()
        stt.model = Mock()
        stt.sample_rate = 16000
        stt._recognizer_factory = Mock(return_value=Mock())
        stt._command_phrases = ["ساعت چنده"]
        stt._grammar = None
        stt._dynamic_graph = True
        stt.grammar_enabled = True
        stt.set_command_mode(True)
        grammar = json.loads(stt._recognizer_factory.call_args.args[2])
        self.assertIn("[unk]", grammar)
        self.assertIn("ساعت چنده", grammar)
        stt.set_command_mode(False)
        stt._recognizer_factory.assert_called_with(stt.model, 16000)

    def test_input_gain_clips_instead_of_wrapping_pcm_samples(self):
        import numpy as np
        stt = self.make_stt()
        stt.input_gain = 3.0
        stt._callback(np.array([20000, -20000], dtype=np.int16).tobytes(), 2, None, None)
        pcm, volume = stt.queue.get_nowait()
        self.assertEqual(np.frombuffer(pcm, dtype=np.int16).tolist(), [32767, -32768])
        self.assertEqual(volume, 20000)


class WorkerTests(unittest.TestCase):
    def test_microphone_test_does_not_execute_recognized_commands(self):
        service = AssistantService()
        stt = Mock(device=None, input_gain=1.0, grammar_enabled=True)
        assistant = Mock(mode="SYSTEM", session_active=False)
        def listen(**kwargs):
            if stt.listen.call_count == 1:
                return "مرورگر رو باز کن"
            service.shutdown()
        stt.listen.side_effect = listen
        service.submit("test_microphone", enabled=True, device=None, gain=1.0, grammar=True)
        with patch("core.stt.SpeachToText", return_value=stt), patch("core.assistant.Assistant", return_value=assistant), \
                patch("core.commands_loader.load_commands", return_value={}), patch("core.service.emit_event") as event:
            service.run()
        assistant.process_text.assert_not_called()
        event.assert_any_call("test_transcript", text="مرورگر رو باز کن")
        stt.stop.assert_called()

    def test_typed_command_works_with_microphone_paused(self):
        service = AssistantService()
        stt = Mock()
        assistant = Mock(mode="SYSTEM", session_active=False)
        assistant.process_text.side_effect = lambda *args, **kwargs: service.shutdown()
        service.submit("text", text="ساعت چنده")
        with patch("core.stt.SpeachToText", return_value=stt), patch("core.assistant.Assistant", return_value=assistant), \
                patch("core.commands_loader.load_commands", return_value={}):
            service.run()
        assistant.process_text.assert_called_once_with("ساعت چنده", activated=True)
        stt.listen.assert_not_called()

    def test_audio_settings_preserve_personal_configuration(self):
        import yaml
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            path = Path(folder) / "config.yaml"
            path.write_text("ai:\n  api_key: private-test-value\naudio:\n  model_path: custom-model\n", encoding="utf-8")
            with patch.object(config, "CONFIG_DIR", Path(folder)), patch.object(config, "CONFIG_PATH", path):
                config.save_audio_settings({"input_gain": 1.5, "microphone_index": 2})
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(data["ai"]["api_key"], "private-test-value")
            self.assertEqual(data["audio"], {"model_path": "custom-model", "input_gain": 1.5, "microphone_index": 2})


if __name__ == "__main__":
    unittest.main()
