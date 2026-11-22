"""Use a locally installed Ollama model to interpret typed task requests."""
from contextlib import closing
from http.client import HTTPConnection, HTTPException
import json
import os
import re
import shutil
import subprocess
import time

from core.tasks import APPS, APP_NAMES, FOLDERS, FOLDER_NAMES, MAX_STEPS, SEPARATOR, make_step, split_task
from core.text import normalize_text


INTENTS = {
    "open_app": r"باز|بیار بالا|بیاور بالا|open|launch",
    "open_folder": r"باز|بیار بالا|بیاور بالا|open",
    "create_folder": r"پوشه.*(?:بساز|درست کن|ایجاد کن)|(?:create|make).*folder",
    "write_note": r"یادداشت.*(?:بنویس|ذخیره کن|بساز)|(?:save|write).*note",
    "find_file": r"پیدا کن|find",
    "web_search": r"جست\s*و?\s*جو|سرچ|search",
    "set_volume": r"صدا.*درصد|volume.*(?:percent|%)",
}
SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "maxItems": MAX_STEPS,
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(INTENTS)},
                    "value": {"type": "string"},
                    "folder": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["kind", "value", "folder", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["steps"],
    "additionalProperties": False,
}
INSTRUCTION = f"""Convert the user's Persian or English request into a complete ordered list of desktop actions.
Only act on explicit requests to do something. For questions, examples, negations, missing details,
or if any part requires an unsupported operation, return {{"steps":[]}}. Never substitute a different action.
Every step has kind, value, folder and text. Set unused fields to empty strings.
open_app: value must be one of {", ".join(APPS)}.
open_folder: value must be one of {", ".join(FOLDERS)}.
create_folder and find_file: folder must be one of {", ".join(FOLDERS)} and value is the user's literal name.
write_note: same folder and filename rules, plus the plain text the user requested in text.
Copy supplied note text verbatim. If the note text is missing, return no steps.
Use documents if the user omitted a folder for create_folder or write_note. For find_file require a folder.
Use a filename only, never a path. web_search: value is the search query, only for an explicit web search.
set_volume: value is an explicitly requested percent as a digit string from 0 through 100.
Return at most {MAX_STEPS} steps and no other fields.
Example: «نوت پد رو بیار بالا» becomes {{"steps":[{{"kind":"open_app","value":"notepad","folder":"","text":""}}]}}.
Example: «روی دسکتاپ پوشه پروژه بساز» becomes {{"steps":[{{"kind":"create_folder","value":"پروژه","folder":"desktop","text":""}}]}}."""


def mentions(text, phrase):
    phrase = normalize_text(phrase)
    return bool(phrase and re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def verified_step(clause, step):
    """Require the request to support the operation and its concrete arguments."""
    kind, value = step["kind"], step["value"]
    if not isinstance(value, str) or kind not in INTENTS:
        return None
    normalized = normalize_text(clause)
    if not re.search(INTENTS[kind], normalized):
        return None
    folders = {folder for alias, folder in FOLDER_NAMES.items() if mentions(normalized, alias)}
    if kind == "open_app":
        if any(mentions(normalized, alias) for alias in APP_NAMES.get(value, ())):
            return make_step(kind, value)
    elif kind == "open_folder":
        if folders == {value}:
            return make_step(kind, value)
    elif kind == "set_volume":
        if re.search(r"(?<!\w)" + re.escape(value) + r"\s+(?:درصد|percent)\b", normalized):
            return make_step(kind, value)
    elif kind == "web_search":
        if mentions(normalized, value):
            return make_step(kind, value)
    else:
        folder = step["folder"]
        text = step["text"] if kind == "write_note" else ""
        default_folder = "documents" if kind != "find_file" else ""
        if ((folders == {folder} or not folders and folder == default_folder)
                and value and value in clause and (not text or text in clause)):
            return make_step(kind, value, folder, text)
    return None


def request_json(path, payload=None, timeout=2):
    with closing(HTTPConnection("127.0.0.1", 11434, timeout=timeout)) as connection:
        method = "POST" if payload is not None else "GET"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        connection.request(method, path, body, {"Content-Type": "application/json"})
        with connection.getresponse() as response:
            if response.status != 200:
                raise OSError(f"Ollama HTTP {response.status}")
            return json.loads(response.read(131072))


class LocalTaskPlanner:
    def __init__(self, model):
        self.model = model
        self.server = None

    def installed_models(self):
        try:
            return request_json("/api/tags").get("models", [])
        except (OSError, HTTPException, ValueError):
            executable = shutil.which("ollama") if os.name == "nt" else None
            if executable is None:
                raise
            if self.server is None or self.server.poll() is not None:
                environment = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NO_CLOUD": "1"}
                self.server = subprocess.Popen(
                    [executable, "serve"], env=environment, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            for _ in range(12):
                time.sleep(.2)
                try:
                    return request_json("/api/tags", timeout=.4).get("models", [])
                except (OSError, HTTPException, ValueError):
                    if self.server.poll() is not None:
                        break
            raise

    def plan(self, text):
        if not self.model or len(text) > 2000:
            return []
        clauses = split_task(text, SEPARATOR + r"|(?<!\w)و(?!\w)")
        if (len(clauses) > MAX_STEPS or any(not clause for clause in clauses)
                or any(not any(re.search(hint, normalize_text(clause)) for hint in INTENTS.values())
                       for clause in clauses)):
            return []
        models = self.installed_models()
        if not any(item.get("name") == self.model for item in models):
            raise OSError("مدل محلی در Ollama پیدا نشد.")
        response = request_json("/api/chat", {
            "model": self.model,
            "stream": False,
            "think": False,
            "format": SCHEMA,
            "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 700},
            "messages": [{"role": "system", "content": INSTRUCTION},
                         {"role": "user", "content": text}],
        }, timeout=30)
        plan = json.loads(response["message"]["content"])
        steps = plan["steps"]
        if not isinstance(steps, list) or len(steps) > MAX_STEPS:
            raise ValueError("طرح اجرا معتبر نیست.")
        if len(steps) != len(clauses):
            return []
        verified = [verified_step(clause, step) for clause, step in zip(clauses, steps, strict=True)]
        return verified if all(verified) else []
