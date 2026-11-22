"""Persian normalization shared by wake words and command matching."""
import re
import unicodedata

_TRANSLATION = str.maketrans("يكۀةؤأإٱ۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "یکههوااا01234567890123456789")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().translate(_TRANSLATION)
    text = text.replace("\u200c", " ").replace("\u200d", " ").replace("ـ", "")
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
