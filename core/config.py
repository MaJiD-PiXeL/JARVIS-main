"""Settings: defaults < bundled config < user config < environment API keys."""
import copy
import os
from pathlib import Path
import sys
from dotenv import load_dotenv
import yaml

load_dotenv()
APP_NAME = "Jarvis"
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
CONFIG_DIR = Path(os.getenv("JARVIS_CONFIG_DIR") or Path(os.getenv("LOCALAPPDATA") or Path.home()) / APP_NAME)
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DEFAULT_CONFIG = {
    "assistant": {"language": "fa", "wakeword": "جارویس", "wakeword_aliases": ["جارویس", "جارویز", "جار ویس", "جرویس", "سرویس", "jarvis"], "command_timeout": 15, "confidence_threshold": 85},
    "audio": {"model_path": "models/small/vosk-fa", "microphone_index": None, "microphone_sensitivity": 2.5, "silence_timeout": 1.2, "input_gain": 1.0, "command_grammar": True, "min_confidence": 0.55},
    "tts": {"engine": "edge", "voice": "fa-IR-FaridNeural", "rate": "+0%", "system_voice_id": ""},
    "ai": {"enabled": True, "provider": "gemini", "api_key": "", "model": "gemini-3-flash-preview"},
    "tasks": {"local_model": "qwen3:4b-instruct"},
    "music": {"path": None},
}


def load_config():
    result = copy.deepcopy(DEFAULT_CONFIG)
    for path in (RESOURCE_DIR / "config.yaml", CONFIG_PATH):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        if not isinstance(data, dict):
            raise ValueError(f"ساختار فایل تنظیمات صحیح نیست: {path}")
        for section, values in data.items():
            if section in result and isinstance(values, dict):
                result[section].update(values)
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return result


CONFIG = load_config()
WAKEWORD = str(CONFIG["assistant"]["wakeword"])
WAKEWORD_ALIASES = CONFIG["assistant"]["wakeword_aliases"]
COMMAND_TIMEOUT = float(CONFIG["assistant"]["command_timeout"])
CONFIDENCE_THRESHOLD = int(CONFIG["assistant"]["confidence_threshold"])
MODEL_PATH = CONFIG["audio"]["model_path"]
MICROPHONE_INDEX = CONFIG["audio"]["microphone_index"]
MICROPHONE_SENS = float(CONFIG["audio"]["microphone_sensitivity"])
SILENCE_TIMEOUT = float(CONFIG["audio"]["silence_timeout"])
INPUT_GAIN = float(CONFIG["audio"]["input_gain"])
COMMAND_GRAMMAR = bool(CONFIG["audio"]["command_grammar"])
MIN_CONFIDENCE = float(CONFIG["audio"]["min_confidence"])
TTS_ENGINE = CONFIG["tts"]["engine"]
TTS_VOICE = CONFIG["tts"]["voice"]
TTS_RATE = CONFIG["tts"]["rate"]
SYSTEM_VOICE_ID = CONFIG["tts"]["system_voice_id"]
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or CONFIG["ai"]["api_key"]
AI_ENABLED = bool(CONFIG["ai"]["enabled"])
AI_MODEL = CONFIG["ai"]["model"]
LOCAL_TASK_MODEL = CONFIG["tasks"]["local_model"]
MUSICS_DIR = CONFIG["music"]["path"]
AI_ON_PHRASES = ["هوش مصنوعی را فعال کن", "هوش مصنوعی رو فعال کن", "حالت هوش مصنوعی", "بیا صحبت کنیم", "بیا حرف بزنیم", "حالت گفتگو", "حالت گفت و گو"]
AI_OFF_PHRASES = ["هوش مصنوعی را غیرفعال کن", "هوش مصنوعی را غیر فعال کن", "هوش مصنوعی رو غیر فعال کن", "هوش مصنوعی رو خاموش کن", "از هوش مصنوعی خارج شو", "حالت عادی", "حالت دستورات"]
SEPARATORS = ["و بعد", "بعدش", "سپس", "بعد از آن", "بعد از اون", "و"]
FILTERS = ["لطفا", "خواهشا"]


def save_audio_settings(settings):
    """Persist only changed audio settings, retaining the user's other values."""
    import tempfile

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    data = data or {}
    data.setdefault("audio", {}).update(settings)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_DIR, suffix=".yaml", delete=False) as stream:
        temporary = Path(stream.name)
        yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
    try:
        temporary.replace(CONFIG_PATH)
    finally:
        temporary.unlink(missing_ok=True)
