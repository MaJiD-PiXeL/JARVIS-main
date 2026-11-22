from pathlib import Path
import yaml
from core import actions
from core.config import CONFIG_DIR, RESOURCE_DIR


def load_commands():
    # Localized defaults are always available; user phrases extend them.
    commands = {}
    for path in (RESOURCE_DIR / "commands.yaml", Path(CONFIG_DIR) / "commands.yaml"):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        if not isinstance(data, dict):
            raise ValueError(f"ساختار فایل فرمان ها صحیح نیست: {path}")
        for action_name, settings in data.items():
            action = getattr(actions, action_name, None)
            phrases = settings.get("phrases", []) if isinstance(settings, dict) else []
            if not callable(action) or not isinstance(phrases, list):
                continue
            phrases = tuple(p for p in phrases if isinstance(p, str) and p.strip())
            if phrases:
                commands[phrases] = action
    if not commands:
        raise RuntimeError("هیچ فرمانی بارگذاری نشد. فایل commands.yaml را بررسی کنید.")
    return commands
