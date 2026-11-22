import json
import queue
import time
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import sounddevice as sd
from core import config
from core.command_router import NEGATION
from core.events import emit_event
from core.text import normalize_text


def resource_path(relative):
    path = Path(relative)
    return path if path.is_absolute() else config.RESOURCE_DIR / path


class SpeachToText:
    def __init__(self, model_path):
        path = resource_path(model_path)
        if not (path / "am" / "final.mdl").exists():
            raise FileNotFoundError(
                f"مدل تشخیص گفتار فارسی پیدا نشد: {path}؛ ابتدا python scripts/download_fa_model.py را اجرا کنید."
            )
        from vosk import Model, KaldiRecognizer

        self.model = Model(str(path))
        self.sample_rate = 16000
        self._recognizer_factory = KaldiRecognizer
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True)
        self.device = config.MICROPHONE_INDEX
        self.input_gain = max(1.0, min(3.0, config.INPUT_GAIN))
        self.grammar_enabled = config.COMMAND_GRAMMAR
        self._grammar = None
        self._command_phrases = []
        self._command_mode = False
        self._dynamic_graph = (path / "graph" / "HCLr.fst").exists()
        self.stream = None
        self.active = False
        self.queue = queue.Queue(maxsize=100)
        self.noise_floor = 40.0
        self._last_voice = None
        self._utterance_start = None
        self._partial = ""
        self._open_recognizer = None
        self._segments = []
        self._open_segments = []

    def set_command_phrases(self, phrases):
        """Bias a dynamic Vosk model toward commands, retaining unknown speech."""
        candidates = {normalize_text(p) for p in phrases if p.strip()}
        # Negations must remain recognizable with a restricted vocabulary.
        candidates.update({"نه", "نکن", "نکنید", "نبند", "نرو", "نمیخوام", "نمی خواهم", "تایید نمی کنم"})
        for phrase in list(candidates):
            for positive, negative in (("کن", "نکن"), ("ببند", "نبند"), ("شو", "نشو")):
                words = phrase.split()
                if positive in words:
                    candidates.add(" ".join(negative if word == positive else word for word in words))
        # Out-of-vocabulary tokens cannot be added to a Vosk grammar.
        self._command_phrases = sorted(p for p in candidates if all(self.model.vosk_model_find_word(w) >= 0 for w in p.split()))

    def set_command_mode(self, enabled):
        self._command_mode = enabled
        grammar = self._command_phrases if enabled and self.grammar_enabled and self._dynamic_graph else None
        if grammar == self._grammar:
            return
        self._grammar = grammar
        self.discard_audio()
        self._rebuild_recognizer()
        emit_event("recognition_mode", constrained=grammar is not None)

    def _rebuild_recognizer(self):
        args = [self.model, self.sample_rate]
        self._open_recognizer = None
        if self._grammar is not None:
            self._open_recognizer = self._recognizer_factory(*args)
            self._open_recognizer.SetWords(True)
            args.append(json.dumps([*self._grammar, "[unk]"], ensure_ascii=False))
        self.recognizer = self._recognizer_factory(*args)
        self.recognizer.SetWords(True)

    def configure_input(self, device, gain, grammar_enabled):
        self.stop()
        self.discard_audio()
        self.device = device
        self.input_gain = max(1.0, min(3.0, float(gain)))
        self.grammar_enabled = grammar_enabled
        self.noise_floor = 40.0
        self.set_command_mode(self._command_mode)

    def _callback(self, indata, frames, time_info, status):
        samples = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
        volume = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
        emit_event("audio_level", level=min(1.0, volume / 6000), clipping=bool(samples.size and np.max(np.abs(samples)) >= 32000))
        if volume < max(150, self.noise_floor * config.MICROPHONE_SENS):
            self.noise_floor = .95 * self.noise_floor + .05 * volume
        try:
            gain = getattr(self, "input_gain", 1.0)
            data = np.clip(samples * gain, -32768, 32767).astype(np.int16).tobytes() if gain != 1 else bytes(indata)
            self.queue.put_nowait((data, volume))
        except queue.Full:
            # Keep recent audio; processing stale speech makes commands lag.
            try:
                self.queue.get_nowait()
                self.queue.put_nowait((data, volume))
            except (queue.Empty, queue.Full):
                pass

    def start(self):
        if self.active:
            return
        rate = 16000
        try:
            sd.check_input_settings(device=self.device, samplerate=rate, channels=1, dtype="int16")
        except sd.PortAudioError:
            rate = int(sd.query_devices(self.device, "input")["default_samplerate"])
        if rate != self.sample_rate:
            self.sample_rate = rate
            self._rebuild_recognizer()
        self.stream = sd.RawInputStream(samplerate=rate, blocksize=int(rate / 10), dtype="int16", channels=1,
                                        device=self.device, callback=self._callback)
        try:
            self.stream.start()
        except Exception:
            self.stream.close()
            self.stream = None
            raise
        self.active = True

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.stop()
            finally:
                self.stream.close()
        self.stream = None
        self.active = False

    def discard_audio(self):
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        self._reset_utterance()

    def _reset_utterance(self):
        self.recognizer.Reset()
        if open_recognizer := getattr(self, "_open_recognizer", None):
            open_recognizer.Reset()
        self._segments = []
        self._open_segments = []
        self._last_voice = None
        self._utterance_start = None
        self._partial = ""
        emit_event("partial", text="")

    @property
    def utterance_in_progress(self):
        return self._last_voice is not None

    @contextmanager
    def suspended(self):
        self.stop()
        self.discard_audio()
        try:
            yield
        finally:
            self.discard_audio()

    @staticmethod
    def _transcript(payload, segments=()):
        results = [*segments, json.loads(payload)]
        text = " ".join(result["text"].strip() for result in results if result.get("text", "").strip())
        words = [word for result in results for word in result.get("result", [])]
        confidence = sum(word.get("conf", 1) for word in words) / len(words) if words else 1.0
        return text, confidence

    def _result(self, payload, open_payload=None):
        text, confidence = self._transcript(payload, getattr(self, "_segments", ()))
        if open_payload is not None:
            free_text, free_confidence = self._transcript(open_payload, self._open_segments)
            # Prefer the actual dictation. Use the command vocabulary for a
            # weak decode only when it agrees with the words we did hear.
            free_words = set(normalize_text(free_text.replace("[unk]", "")).split())
            command_words = set(normalize_text(text.replace("[unk]", "")).split())
            matches = free_words & command_words
            common = {"رو", "را", "کن", "باز", "شو", "و", "این", "من", "یه", "یک", "بده"}
            compatible = bool(matches - common) and len(free_words - command_words) <= 1
            use_command = (text and "[unk]" not in text and confidence >= max(.8, config.MIN_CONFIDENCE)
                           and free_confidence < config.MIN_CONFIDENCE
                           and compatible and not NEGATION.search(normalize_text(free_text)))
            if not use_command:
                text, confidence = free_text, free_confidence
        self._reset_utterance()
        if not text:
            return None
        if "[unk]" in text or confidence < config.MIN_CONFIDENCE:
            emit_event("uncertain", text=text.replace("[unk]", "…"), confidence=confidence)
            return None
        emit_event("confidence", value=confidence)
        return text

    def listen(self, timeout=12, silence_timeout=1.2, interrupted=None):
        self.start()
        open_recognizer = getattr(self, "_open_recognizer", None)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if interrupted is not None and interrupted():
                return None
            try:
                data, volume = self.queue.get(timeout=min(.1, max(.001, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if volume > max(150, self.noise_floor * config.MICROPHONE_SENS):
                self._last_voice = time.monotonic()
            if self.recognizer.AcceptWaveform(data):
                self._segments.append(json.loads(self.recognizer.Result()))
            if open_recognizer is not None and open_recognizer.AcceptWaveform(data):
                self._open_segments.append(json.loads(open_recognizer.Result()))
            display = open_recognizer or self.recognizer
            segments = self._open_segments if open_recognizer is not None else self._segments
            partial = " ".join([*(segment.get("text", "") for segment in segments),
                                json.loads(display.PartialResult()).get("partial", "")]).strip()
            if partial != self._partial:
                self._partial = partial
                emit_event("partial", text=partial.replace("[unk]", "…"))
            if partial and self._last_voice is None:
                self._last_voice = time.monotonic()
            if self._last_voice is not None and self._utterance_start is None:
                self._utterance_start = self._last_voice
            if self._last_voice is not None and time.monotonic() - self._last_voice > silence_timeout:
                open_result = open_recognizer.FinalResult() if open_recognizer is not None else None
                return self._result(self.recognizer.FinalResult(), open_result)
            if self._utterance_start is not None and time.monotonic() - self._utterance_start > 20:
                self._reset_utterance()
                if partial:
                    emit_event("uncertain", text=partial.replace("[unk]", "…"), confidence=0.0)
                return None
        # Keep partial recognition across idle listening windows.
        return None
