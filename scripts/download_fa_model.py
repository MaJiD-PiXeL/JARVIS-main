"""Install the official small Persian Vosk model without changing other models."""

import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "vosk-model-small-fa-0.42"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
DESTINATION = ROOT / "models" / "small" / "vosk-fa"


def install():
    if (DESTINATION / "am" / "final.mdl").exists():
        print("مدل فارسی از قبل نصب است:", DESTINATION)
        return
    if DESTINATION.exists():
        raise RuntimeError(f"پوشه مدل ناقص است؛ آن را بررسی کنید: {DESTINATION}")
    downloads = ROOT / ".downloads"
    downloads.mkdir(exist_ok=True)
    archive = downloads / f"{MODEL_NAME}.zip"
    if not archive.exists() or not zipfile.is_zipfile(archive):
        print("در حال دریافت مدل فارسی از", MODEL_URL)
        partial = archive.with_suffix(".zip.part")
        with urllib.request.urlopen(MODEL_URL, timeout=120) as source, partial.open("wb") as output:
            shutil.copyfileobj(source, output)
        partial.replace(archive)
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with tempfile.TemporaryDirectory(prefix="vosk_fa_", dir=downloads) as folder:
        staging = Path(folder).resolve()
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                target = (staging / entry.filename).resolve()
                if not target.is_relative_to(staging) or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise RuntimeError("مسیر نامعتبر در فایل مدل")
            package.extractall(staging)
        source = staging / MODEL_NAME
        if not (source / "am" / "final.mdl").exists() or not (source / "conf" / "model.conf").exists():
            raise RuntimeError("ساختار مدل دانلودشده صحیح نیست")
        DESTINATION.parent.mkdir(parents=True, exist_ok=True)
        source.rename(DESTINATION)
    (DESTINATION / "SOURCE.txt").write_text(
        f"Official model: {MODEL_URL}\nLicense: Apache-2.0 (Vosk model catalogue)\nArchive SHA256: {digest}\n",
        encoding="utf-8",
    )
    print("مدل فارسی نصب شد:", DESTINATION)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        install()
    except Exception as error:
        print("نصب مدل فارسی ناموفق بود:", error)
        sys.exit(1)
