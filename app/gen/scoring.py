from __future__ import annotations

import math
import re
from typing import Dict, Tuple


EMOTION_WORDS = {
    "amazing",
    "powerful",
    "broken",
    "love",
    "hate",
    "win",
    "fear",
    "delight",
    "frustration",
    "excited",
}


def _hook_quality(text: str) -> int:
    first = text.strip().splitlines()[0] if text.strip() else ""
    score = 0
    if first.endswith("?"):
        score += 15
    if re.match(r"^(\d+|how|why|what|vs\.)\b", first.lower()):
        score += 10
    return min(score, 25)


def _structure_score(text: str) -> int:
    paras = [p for p in [p.strip() for p in text.split("\n\n")] if p]
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    score = 0
    if 2 <= len(paras) <= 4:
        score += 10
    if len(first_line.split()) <= 10:
        score += 10
    if all(len(p.split()) <= 60 for p in paras):
        score += 5
    return min(score, 20)


def _emotion_density(text: str) -> int:
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    if not tokens:
        return 0
    hits = sum(1 for t in tokens if t in EMOTION_WORDS)
    rate = hits / max(len(tokens), 1)
    return min(int(rate * 100), 15)


def _cta(text: str) -> int:
    last = text.strip().splitlines()[-1] if text.strip() else ""
    if last.endswith("?"):
        return 15
    if re.search(r"(let me know|what do you think|agree\?|thoughts\?)", last.lower()):
        return 15
    return 0


def _readability(text: str) -> int:
    sentences = max(1, text.count(".") + text.count("!") + text.count("?"))
    words = max(1, len(re.findall(r"\b\w+\b", text)))
    syllables = max(1, sum(max(1, len(re.findall(r"[aeiouy]+", w.lower()))) for w in re.findall(r"\b\w+\b", text)))
    flesch = 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)
    target = 70
    diff = abs(flesch - target)
    return max(0, 10 - int(diff / 5))


def _topicality(text: str, keywords: dict[str, float]) -> int:
    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    overlap = [keywords[k] for k in keywords.keys() if k in tokens]
    score = int(min(sum(overlap) * 100, 15))
    return score


def score_text(text: str, today_keywords: dict[str, float] | None = None) -> Tuple[int, Dict[str, int]]:
    breakdown = {
        "hook": _hook_quality(text),
        "structure": _structure_score(text),
        "emotion": _emotion_density(text),
        "cta": _cta(text),
        "topicality": _topicality(text, today_keywords or {}),
        "readability": _readability(text),
    }
    total = sum(breakdown.values())
    return total, breakdown

