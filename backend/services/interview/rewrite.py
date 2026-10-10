"""Rewrites the user's own answer into STAR form (their facts, under 200 words). Owner: M3.

Missing elements become bracketed prompts ("[Add the result: ...]"), never invented content.
Without an LLM, the fallback assembles the found quotes into the STAR structure with the same prompts.
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from backend.llm_adapter import complete_json
from backend.schemas.interview import StarScore
from backend.services.interview.fillers import filler_spans
from backend.services.interview.star import ELEMENTS

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "rewrite_star.md"
MAX_WORDS = 200

MISSING_PROMPTS = {
    "situation": "[Add the situation: where you were and what was going on, in one sentence]",
    "task": "[Add your task: what you personally had to achieve]",
    "action": "[Add your actions: two or three concrete steps you took yourself, and the tools you used]",
    "result": "[Add the result: what changed, ideally with a number - time saved, accuracy, grade, feedback]",
}


class _Rewrite(BaseModel):
    answer: str = Field(description="The rewritten STAR answer, at most 200 words.")


def rewrite_answer(question: str, transcript: str, star: StarScore) -> str:
    if not transcript.strip():
        return ""
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        question=question, transcript=transcript, star_summary=star_summary(star)
    )
    try:
        text = complete_json(prompt, _Rewrite, temperature=0.4, max_tokens=800).answer.strip()
    except Exception:  # LLMError, or a missing provider package / API key
        return fallback_rewrite(star)
    return _limit_words(text, MAX_WORDS) if text else fallback_rewrite(star)


def star_summary(star: StarScore) -> str:
    lines = []
    for name in ELEMENTS:
        el = getattr(star, name)
        lines.append(f'- {name.title()}: present, "{el.evidence_span}"' if el.present else f"- {name.title()}: MISSING")
    return "\n".join(lines)


def fallback_rewrite(star: StarScore) -> str:
    """The user's own quotes, cleaned of fillers, in STAR order, with prompts for what is missing."""
    parts = []
    for name in ELEMENTS:
        el = getattr(star, name)
        if el.present:
            clean = strip_fillers(el.evidence_span)
            parts.append(clean[0].upper() + clean[1:] if clean else MISSING_PROMPTS[name])
        else:
            parts.append(MISSING_PROMPTS[name])
    return _limit_words("\n\n".join(parts), MAX_WORDS)


def strip_fillers(text: str) -> str:
    """Remove the filler words the counter found and tidy the punctuation they leave behind."""
    for start, end, _ in reversed(filler_spans(text)):
        text = text[:start] + text[end:]
    text = re.sub(r"^[\s,]+", "", text)
    text = re.sub(r"\s*,(\s*,)+", ",", text)  # ",," left by a removed filler
    text = re.sub(r"\b(and|but|then)\s*,\s*", r"\1 ", text, flags=re.I)  # "and like, I" -> "and I"
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return " ".join(text.split()).strip(" ,")


def _limit_words(text: str, n: int) -> str:
    words = text.split(" ")
    return text if len(words) <= n else " ".join(words[:n]).rstrip(",;") + "..."
