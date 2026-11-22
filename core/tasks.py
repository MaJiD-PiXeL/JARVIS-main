"""Plan and execute everyday desktop tasks with a fixed set of operations."""
from dataclasses import dataclass
from functools import partial
import os
from pathlib import PureWindowsPath
import re
import time
from typing import Callable
from urllib.parse import urlencode
import webbrowser

from core.known_folders import FOLDERS, known_folder
from core.text import normalize_text


APPS = {
    "notepad": ("نوت‌پد", "notepad.exe"),
    "calculator": ("ماشین‌حساب", "calc.exe"),
    "explorer": ("فایل اکسپلورر", "explorer.exe"),
    "paint": ("پینت", "mspaint.exe"),
    "settings": ("تنظیمات ویندوز", "ms-settings:"),
    "camera": ("دوربین", "microsoft.windows.camera:"),
    "browser": ("مرورگر", "https://www.google.com/"),
    "youtube": ("یوتیوب", "https://www.youtube.com/"),
}
APP_NAMES = {
    "notepad": ("نوت پد", "نوتپد", "دفترچه یادداشت", "دفتر یادداشت", "notepad"),
    "calculator": ("ماشین حساب", "ماشینحساب", "calculator"),
    "explorer": ("فایل اکسپلورر", "اکسپلورر", "مدیریت فایل", "فایل منیجر", "explorer"),
    "paint": ("پینت", "نقاشی", "paint"),
    "settings": ("تنظیمات", "تنظیمات ویندوز", "settings"),
    "camera": ("دوربین", "camera"),
    "browser": ("مرورگر", "کروم", "گوگل", "browser", "chrome"),
    "youtube": ("یوتیوب", "یوتوب", "youtube"),
}
FOLDER_NAMES = {
    "دسکتاپ": "desktop", "میز کار": "desktop", "desktop": "desktop",
    "اسناد": "documents", "مدارک": "documents", "documents": "documents",
    "دانلود": "downloads", "دانلودها": "downloads", "downloads": "downloads",
    "تصاویر": "pictures", "عکس ها": "pictures", "pictures": "pictures",
    "موسیقی": "music", "music": "music", "ویدیوها": "videos", "videos": "videos",
}
EXAMPLES = (
    "ماشین حساب رو باز کن و بعد نوت پد رو باز کن",
    "روی دسکتاپ پوشه «کارهای امروز» بساز",
    "در اسناد یادداشت «خرید» با متن «شیر و نان» بساز",
    "در دانلودها فایل «گزارش.pdf» را پیدا کن",
    "درباره «تقویم شمسی» جستجو کن",
    "صدا را روی ۳۰ درصد بگذار",
)
MAX_STEPS = 6
SOLO_COMMANDS = {"clean_all_files", "lock_pc", "exit_assistant"}

QUOTED = r'"[^"]*"|«[^»]*»|“[^”]*”'
SEPARATOR = r"(?<!\w)(?:و\s+بعد(?:ش)?|بعد\s+از\s+(?:آن|اون)|بعدش|بعد|سپس)(?!\w)|[؛;]"
LOCATION = r"(?:(?:روی|توی|تو(?:یِ)?|در|داخل)\s+(?:پوشه[ٔ‌ی]?\s+)?(?P<folder>.+?)\s+)?"
QUESTION = re.compile(r"^(?:چطور|چطوری|چگونه|ایا|آیا|اگر|اگه|مثلا|how|what|if)\b")
CASUAL_PREFIX = re.compile(r"^(?:(?:اول|برام|برای من|میشه|می شه|میتونی|می تونی|میخوام|می خوام|میخواستم|می خواستم)\s+)+")
LAUNCH = r"(?:باز(?:ش)? کن(?:ی)?|بیار(?:ی)? بالا|بیاور(?:ی)? بالا|اجرا کن(?:ی)?)"
LAUNCH_AFTER = re.compile(rf"(.+?) (?:را |رو )?(?:برام |برای من )?{LAUNCH}")
LAUNCH_BEFORE = re.compile(rf"{LAUNCH} (.+)")
VOLUME = re.compile(
    r"(?:صدا(?:ی سیستم)?|ولوم) (?:را |رو )?"
    r"(?:(?:روی |رو )?(.+?) درصد (?:کن|بذار|بگذار|تنظیم کن)(?:ی)?|"
    r"(?:بذار|بگذار|تنظیم کن)(?:ی)? (?:روی |رو )?(.+?) درصد)"
)
UNITS = ("صفر", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه")
TEENS = ("ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده")
TENS = ("بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود")
PERCENT_WORDS = {name: value for value, name in enumerate(UNITS + TEENS)}
PERCENT_WORDS.update({name: value * 10 for value, name in enumerate(TENS, 2)})
PERCENT_WORDS.update({f"{ten} و {unit}": tens * 10 + units for tens, ten in enumerate(TENS, 2)
                      for units, unit in enumerate(UNITS[1:], 1)})
PERCENT_WORDS.update({"یه": 1, "صد": 100, "یک صد": 100, "یکصد": 100})


@dataclass(frozen=True)
class Step:
    title: str
    action: Callable
    name: str = ""


def launch_url(url):
    if not webbrowser.open(url):
        raise OSError("مرورگر پیش‌فرض ویندوز باز نشد.")


def open_app(name):
    label, target = APPS[name]
    if target.startswith("https://"):
        launch_url(target)
    elif target.endswith(":"):
        os.startfile(target)
    else:
        windows = os.environ.get("SystemRoot", r"C:\Windows")
        directory = windows if name == "explorer" else os.path.join(windows, "System32")
        os.startfile(os.path.join(directory, target))
    return f"درخواست باز کردن {label} به ویندوز ارسال شد."


def open_folder(folder):
    path = known_folder(folder)
    os.startfile(path)
    return f"پوشه باز شد.\n{path}"


def validate_name(name):
    if (not name or len(name) > 180 or name != name.strip(" .")
            or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in name)
            or PureWindowsPath(name).is_reserved()):
        raise ValueError("نام باید یک نام معتبر ویندوز، بدون مسیر، باشد.")
    return name


def create_folder(folder, name):
    path = known_folder(folder) / name
    try:
        path.mkdir()
    except FileExistsError:
        if path.is_dir():
            return f"پوشه از قبل وجود دارد.\n{path}"
        raise
    return f"پوشه ساخته شد.\n{path}"


def write_note(folder, name, text):
    path = known_folder(folder) / name
    # Exclusive creation preserves any existing file, including concurrent writes.
    with path.open("x", encoding="utf-8") as stream:
        try:
            stream.write(text + "\n")
            stream.flush()
        except OSError:
            stream.close()
            path.unlink(missing_ok=True)
            raise
    return f"یادداشت ذخیره شد.\n{path}"


def find_file(folder, name):
    root = known_folder(folder)
    if not root.is_dir():
        raise FileNotFoundError(root)
    matches = []
    needle = normalize_text(name)
    deadline = time.monotonic() + 4
    unreadable = []
    for directory, children, files in os.walk(root, onerror=unreadable.append):
        if time.monotonic() >= deadline or len(matches) >= 8:
            return "نتیجه‌های جست‌وجوی محدود\n" + ("\n".join(matches[:8]) or "تا اینجا فایلی پیدا نشد.")
        children[:] = [child for child in children if not os.path.isjunction(os.path.join(directory, child))]
        matches.extend(os.path.join(directory, file) for file in files if needle in normalize_text(file))
    if unreadable or len(matches) > 8:
        return "نتیجه‌های جست‌وجوی محدود\n" + ("\n".join(matches[:8]) or "در پوشه‌های قابل دسترسی فایلی پیدا نشد.")
    return "فایل‌های پیدا شده\n" + "\n".join(matches) if matches else f"«{name}» در {FOLDERS[folder][0]} پیدا نشد."


def web_search(query):
    launch_url("https://www.google.com/search?" + urlencode({"q": query}))
    return f"جست‌وجوی «{query}» به مرورگر فرستاده شد."


def set_volume(percent):
    from core.actions.volume import set_volume as apply_volume

    apply_volume(percent / 100)
    return f"صدا روی {percent}٪ تنظیم شد."


def make_step(kind, value, folder="", text=""):
    """Validate every step, including plans produced by the language model."""
    if not all(isinstance(item, str) for item in (kind, value, folder, text)):
        raise ValueError("اطلاعات مرحله معتبر نیست.")
    if kind == "open_app" and value in APPS and not (folder or text):
        return Step(f"باز کردن {APPS[value][0]}", partial(open_app, value), kind)
    if kind == "open_folder" and value in FOLDERS and not (folder or text):
        return Step(f"باز کردن {FOLDERS[value][0]}", partial(open_folder, value), kind)
    if kind == "web_search" and 0 < len(value.strip()) <= 300 and not (folder or text):
        return Step("جست‌وجو در مرورگر", partial(web_search, value.strip()), kind)
    if kind == "set_volume" and not (folder or text) and re.fullmatch(r"[0-9]{1,3}", value):
        percent = int(value)
        if not 0 <= percent <= 100:
            raise ValueError("میزان صدا باید بین صفر و صد درصد باشد.")
        return Step("تنظیم صدا", partial(set_volume, percent), kind)
    if kind in ("create_folder", "write_note", "find_file") and folder in FOLDERS:
        name = validate_name(value)
        if kind == "create_folder" and not text:
            return Step(f"ساخت پوشهٔ {name}", partial(create_folder, folder, name), kind)
        if kind == "find_file" and not text and normalize_text(name):
            return Step(f"پیدا کردن {name}", partial(find_file, folder, name), kind)
        if kind == "write_note" and 0 < len(text.strip()) <= 1800:
            filename = name if name.lower().endswith(".txt") else name + ".txt"
            return Step(f"ذخیرهٔ {filename}", partial(write_note, folder, filename, text), kind)
    raise ValueError("این مرحله با اطلاعات داده‌شده قابل اجرا نیست.")


def split_task(text, separator=SEPARATOR):
    pieces = []
    start = 0
    for match in re.finditer(rf"(?:{QUOTED})|(?P<split>{separator})", text):
        if match.group("split"):
            pieces.append(text[start:match.start()].strip())
            start = match.end()
    return [*pieces, text[start:].strip()]


def is_question(text):
    return text.endswith(("؟", "?")) or bool(QUESTION.match(normalize_text(text)))


def unquote(text):
    text = text.strip()
    return text[1:-1] if re.fullmatch(QUOTED, text) else text


def launch_target(normalized):
    if match := LAUNCH_AFTER.fullmatch(normalized) or LAUNCH_BEFORE.fullmatch(normalized):
        return match[1]
    return ""


def launch_step(name):
    for key, aliases in APP_NAMES.items():
        if name in aliases:
            return make_step("open_app", key)
    if name in FOLDER_NAMES:
        return make_step("open_folder", FOLDER_NAMES[name])
    return None


def parse_step(text, router):
    text = re.sub(r"^(?:لطفاً?|خواهشاً?)\s+", "", text.strip()).rstrip("؟?!،.")
    action = router.match(text)
    if action:
        return Step(text, action, action.__name__)
    normalized = CASUAL_PREFIX.sub("", router.normalize(text.replace("%", " درصد ").replace("٪", " درصد ")))
    if step := launch_step(launch_target(normalized)):
        return step
    if action := router.match(normalized):
        return Step(text, action, action.__name__)
    if match := VOLUME.fullmatch(normalized):
        number = match[1] or match[2]
        if number in PERCENT_WORDS:
            number = str(PERCENT_WORDS[number])
        if number.isascii() and number.isdigit():
            return make_step("set_volume", number)
    named = rf"(?P<name>{QUOTED}|[^«»“”\"؟!]+?)"
    ending = r"(?:را |رو )?(?:بساز|درست کن|ایجاد کن)"
    patterns = (
        ("create_folder", rf"{LOCATION}(?:یک |یه )?پوشه(?:‌ای)?(?: (?:به )?اسم| به نام)?\s+{named}\s+{ending}"),
        ("write_note", rf"{LOCATION}(?:یک |یه )?یادداشت(?: (?:به )?اسم| به نام)?\s+{named}\s+(?:(?:را|رو)\s+)?با متن\s+(?P<text>{QUOTED}|.+?)\s+(?:را |رو )?(?:بساز|بنویس|ذخیره کن)"),
        ("find_file", rf"{LOCATION}فایل\s+{named}\s+(?:را |رو )?پیدا کن"),
        ("web_search", rf"(?:درباره(?:ٔ|‌ی)? |در مورد |برای ){named}\s+(?:را |رو )?(?:جست[‌ ]?و?[‌ ]?جو|سرچ) کن"),
        ("web_search", rf"(?P<name>{QUOTED})\s+(?:را |رو )?(?:جست[‌ ]?و?[‌ ]?جو|سرچ) کن"),
    )
    for kind, pattern in patterns:
        if match := re.fullmatch(pattern, text):
            parts = match.groupdict()
            folder = FOLDER_NAMES.get(normalize_text(parts.get("folder") or "اسناد"), "")
            return make_step(kind, unquote(parts["name"]), "" if kind == "web_search" else folder,
                             unquote(parts.get("text") or ""))
    return None


def local_plan(text, router):
    phrases = split_task(text)
    if action := router.match(text):
        return [Step(text, action, action.__name__)]
    if len(phrases) == 1:
        if direct := parse_step(text, router):
            return [direct]
        target = launch_target(CASUAL_PREFIX.sub("", router.normalize(text)))
        if " و " in target:
            targets = target.split(" و ")
            if len(targets) > MAX_STEPS:
                raise ValueError(f"در هر درخواست حداکثر {MAX_STEPS} مرحله بفرست.")
            steps = [launch_step(name) for name in targets]
            if all(steps):
                return steps
        phrases = split_task(text, r"(?<!\w)و(?!\w)")
        if len(phrases) < 2:
            return []
    if len(phrases) > MAX_STEPS:
        raise ValueError(f"در هر درخواست حداکثر {MAX_STEPS} مرحله بفرست.")
    steps = [parse_step(phrase, router) for phrase in phrases]
    if any(step is None for step in steps):
        return []
    if any(step.name in SOLO_COMMANDS for step in steps):
        raise ValueError("قفل صفحه، خروج و پاک‌سازی را جداگانه درخواست کن.")
    return steps
