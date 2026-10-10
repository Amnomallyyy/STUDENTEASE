"""Filler-word counter. Pure code, no LLM, so judges can verify every number. Owner: M3.

"um", "uh", "er", "erm", "you know", "basically", "actually", "literally", "i mean", "kind of" and
"sort of" always count. "like" and "so" are also normal words, so they only count where they are
used as fillers:
    like  - between commas, after another filler, or after a linking word ("and like", "was like")
            but not "I would like", "looks like", "something like"
    so    - at the start of a sentence or clause ("So, I ...", ". So we ..."), not "so that" / "so much"
frontend/src/lib/fillers.ts runs the same rules for the live gauge.
"""
from __future__ import annotations

import re

ALWAYS = ["um", "uh", "er", "erm", "uhm", "you know", "basically", "actually", "literally", "i mean", "kind of", "sort of"]

_ALWAYS_RE = re.compile(r"\b(" + "|".join(re.escape(f) for f in sorted(ALWAYS, key=len, reverse=True)) + r")\b", re.I)
_WORD_RE = re.compile(r"[A-Za-z']+")
# Words after which "like" is a filler ("and like", "was like", "um like").
_LIKE_AFTER = {"and", "but", "was", "is", "were", "it's", "its", "um", "uh", "er", "erm", "just"}
_SO_NOT_BEFORE = {"that", "much", "many", "far", "long"}

# 0 penalty at or below 2 fillers per 100 words, full penalty at 12 or more.
FREE_PER_100 = 2.0
MAX_PER_100 = 12.0


def filler_spans(text: str) -> list[tuple[int, int, str]]:
    """(start, end, filler) for every filler in `text`, in order."""
    spans = [(m.start(), m.end(), m.group(1).lower()) for m in _ALWAYS_RE.finditer(text)]
    words = list(_WORD_RE.finditer(text))
    for i, m in enumerate(words):
        w = m.group(0).lower()
        before = text[: m.start()].rstrip()
        after = text[m.end():].lstrip()
        prev = words[i - 1].group(0).lower() if i else ""
        nxt = words[i + 1].group(0).lower() if i + 1 < len(words) else ""
        if w == "like" and (before.endswith(",") or after.startswith(",") or (prev in _LIKE_AFTER and not before.endswith((".", "!", "?")))):
            spans.append((m.start(), m.end(), "like"))
        elif w == "so" and (not before or before.endswith((".", "!", "?", ",", ";"))) and nxt not in _SO_NOT_BEFORE:
            spans.append((m.start(), m.end(), "so"))
    return sorted(spans)


def count_fillers(text: str) -> dict[str, int]:
    """Filler counts by word, e.g. {"um": 2, "like": 1}. Empty dict for a clean answer."""
    counts: dict[str, int] = {}
    for _, _, word in filler_spans(text):
        counts[word] = counts.get(word, 0) + 1
    return counts


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def fillers_per_100_words(counts: dict[str, int], words: int) -> float:
    return round(100 * sum(counts.values()) / words, 1) if words else 0.0


def filler_score(per_100: float) -> float:
    """0-100, where 100 means no distracting fillers (up to 2 per 100 words is normal speech)."""
    if per_100 <= FREE_PER_100:
        return 100.0
    return round(max(0.0, 100 * (1 - (per_100 - FREE_PER_100) / (MAX_PER_100 - FREE_PER_100))), 1)
