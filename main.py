import sys
from pathlib import Path
import subprocess


def project_interpreter():
    """Use this project's installed environment when launched by Windows Python."""
    if getattr(sys, "frozen", False):
        return None
    environment = Path(__file__).resolve().parent / ".venv"
    executable = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if executable.is_file() and Path(sys.prefix).resolve() != environment.resolve():
        return executable
    return None


def show_startup_error(message):
    if sys.platform == "win32" and not any(arg in sys.argv[1:] for arg in ("--console", "--check")):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "NEXORA · خطای راه‌اندازی جارویس", 0x10)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    interpreter = project_interpreter()
    if interpreter is not None:
        try:
            return subprocess.call([str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]])
        except KeyboardInterrupt:
            return 130

    stt = None
    try:
        if "--check" not in sys.argv[1:] and "--console" not in sys.argv[1:]:
            from core.gui import launch_gui
            return launch_gui()
        from core import config
        from core.stt import SpeachToText
        from core.assistant import Assistant
        from core.commands_loader import load_commands

        commands = load_commands()
        stt = SpeachToText(config.MODEL_PATH)
        if "--check" in sys.argv[1:]:
            print("بررسی راه اندازی موفق بود؛ محیط پایتون، فرمان ها و مدل فارسی آماده اند.")
            print("پایتون:", sys.executable)
            return 0
        assistant = Assistant(stt, commands)
        assistant.run()
    except KeyboardInterrupt:
        print("جارویس متوقف شد.")
    except ModuleNotFoundError as error:
        message = f"بسته مورد نیاز نصب نیست: {error.name}"
        print(message)
        print("برای نصب وابستگی ها، این دستور را اجرا کنید:")
        print(f'"{sys.executable}" -m pip install -r "{Path(__file__).resolve().parent / "requirements.txt"}"')
        show_startup_error(message + "\nوابستگی‌های requirements.txt را نصب کنید.")
        return 1
    except Exception as error:
        print("راه اندازی جارویس ناموفق بود:", error)
        show_startup_error("راه‌اندازی جارویس ناموفق بود:\n" + str(error))
        return 1
    finally:
        if stt is not None:
            stt.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
