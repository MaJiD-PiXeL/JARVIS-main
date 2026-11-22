"""Render the real desktop shell without microphone, network, or system actions."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("JARVIS_CONFIG_DIR", str(ROOT / ".test-config"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from core.commands_loader import load_commands
from core.gui import create_application, JarvisWindow

app = create_application()
window = JarvisWindow(start_service=False)
if len(sys.argv) >= 3:
    window.resize(int(sys.argv[1]), int(sys.argv[2]))
else:
    window.resize(1280, 860)
window.on_event("ready", {"voice_available": True, "command_groups": tuple(load_commands())})
window.on_event("state", {"value": "paused"})
window.on_event("response", {"text": "سلام. من جارویس هستم؛ برای شروع، میکروفون را روشن کن یا فرمانت را بنویس."})
window.show()


def capture():
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    destination = output / f"nexora-jarvis-{window.width()}.png"
    window.grab().save(str(destination))
    print(destination)
    window.close()


QTimer.singleShot(350, capture)
sys.exit(app.exec())
