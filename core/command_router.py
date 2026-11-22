import re
from rapidfuzz import fuzz
from core import config
from core.text import normalize_text


NEGATION = re.compile(r"\b(?:نکن|نکنید|نشه|نکنه|نبند|نبندید|نرو|نذار|نذارید|نزن|نشو|نشوید|نمیخوام|نمیخواهم|نمی\s+(?:خوام|خواهم))\b")


class CommandRouter:
    def __init__(self, commands: dict, threshold: int):
        self.commands = commands
        self.threshold = threshold
        self.variants = [(self.normalize(v), a) for variants, a in commands.items() for v in variants]

    def normalize(self, text: str) -> str:
        text = normalize_text(text)
        for filler in config.FILTERS:
            text = re.sub(r"(?<!\w)" + re.escape(normalize_text(filler)) + r"(?!\w)", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def split_phrases(self, text: str) -> list[str]:
        separators = sorted(config.SEPARATORS, key=len, reverse=True)
        pattern = r"(?<!\w)(?:" + "|".join(re.escape(s) for s in separators) + r")(?!\w)"
        return [p.strip() for p in re.split(pattern, text) if p.strip()]

    def match(self, text: str):
        normalized = self.normalize(text)
        return next((action for variant, action in self.variants if normalized == variant), None)

    def detect(self, user_text: str):
        results, used = [], set()
        normalized = self.normalize(user_text)
        exact = next((a for v, a in self.variants if normalized == v), None)
        if exact:
            return [(exact, 100.0, normalized)]
        for phrase in self.split_phrases(normalized):
            if NEGATION.search(phrase):
                continue
            scores = {}
            for variant, action in self.variants:
                score = fuzz.ratio(phrase, variant)
                scores[action] = max(score, scores.get(action, 0))
            ranked = sorted(scores, key=scores.get, reverse=True)
            if not ranked:
                continue
            best_action = ranked[0]
            best_score = scores[best_action]
            second_score = scores[ranked[1]] if len(ranked) > 1 else 0
            if best_score >= self.threshold and best_score - second_score >= 5 and best_action not in used:
                results.append((best_action, best_score, phrase))
                used.add(best_action)
        return results
