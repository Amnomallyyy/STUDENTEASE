"""STAR compliance: which of Situation / Task / Action / Result the answer contains, with a quote for each.

The LLM call uses a strict schema; every quote it returns is then checked against the transcript,
and a quote that is not really there is thrown away, so the model cannot hallucinate a Result.
Without an LLM (no key, no network) a keyword fallback finds the same elements from cue phrases.
frontend/src/lib/starCues.ts runs the same cues for the live checklist. Owner: M3.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel

from backend.llm_adapter import complete_json
from backend.schemas.interview import StarElement, StarScore

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "star_rubric.md"
ELEMENTS = ("situation", "task", "action", "result")

# Cue phrases for the offline fallback (lower case, matched on word boundaries).
CUES: dict[str, list[str]] = {
    "situation": [
        "when i was", "while i was", "at my", "in my", "during my", "during a", "during the", "last year",
        "last semester", "at the time", "in my final year", "in my internship", "at university", "we had a",
        "there was a", "our team was", "i was working", "i worked at", "i was part of",
    ],
    "task": [
        "i needed to", "i had to", "my task", "my goal", "my job was", "i was responsible", "i was asked to",
        "my role was", "the goal was", "the challenge was", "the problem was", "we needed to", "i wanted to",
        "the task was", "i was in charge",
    ],
    "action": [
        "i built", "i created", "i wrote", "i designed", "i decided", "i used", "i led", "i implemented",
        "i analysed", "i analyzed", "i organised", "i organized", "i set up", "i started", "i spoke to",
        "i talked to", "i reached out", "i automated", "i cleaned", "i tested", "i fixed", "i developed",
        "i proposed", "i trained", "i researched", "i made", "i changed", "i coordinated", "so i",
        "i followed", "i asked", "i practised", "i practiced", "i read", "i watched", "i studied", "i contacted", "i reviewed", "i planned", "i broke", "i split", "i prepared", "i scheduled", "i collected", "i compared", "i presented", "i explained", "i suggested", "i negotiated", "i learned how", "i taught", "i worked with",
    ],
    "result": [
        "as a result", "which led to", "this led to", "resulted in", "in the end", "the outcome", "reduced",
        "increased", "improved", "saved", "cut", "grew", "we won", "i learned", "i learnt", "the result",
        "finally", "eventually", "got a", "was praised", "received", "achieved", "percent", "%",
    ],
}


class _StarLLM(BaseModel):
    situation: StarElement
    task: StarElement
    action: StarElement
    result: StarElement


def analyze_star(question: str, transcript: str) -> StarScore:
    """STAR elements with verified quotes. Falls back to cue phrases if the LLM is unavailable."""
    if not transcript.strip():
        return _empty("rules")
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(question=question, transcript=transcript)
    try:
        raw = complete_json(prompt, _StarLLM)
    except Exception:  # LLMError, or a missing provider package / API key
        return rule_based_star(transcript)
    out = {name: ground(getattr(raw, name), transcript) for name in ELEMENTS}
    return StarScore(**out, source="llm")


def ground(element: StarElement, transcript: str) -> StarElement:
    """Keep an element only if its quote is really in the transcript; snap near-quotes to the real text."""
    span = element.evidence_span.strip().strip('"“”')
    if not element.present or not span:
        return StarElement(present=False, evidence_span="", strength=0)
    found = find_span(span, transcript)
    if found is None:
        return StarElement(present=False, evidence_span="", strength=0)
    return StarElement(present=True, evidence_span=found, strength=max(1, element.strength))


def find_span(span: str, transcript: str, min_ratio: float = 0.85) -> str | None:
    """The transcript text matching `span` (exact, case/space-insensitive, or a near-verbatim quote)."""
    if span in transcript:
        return span
    norm_t, index = _normalise_with_index(transcript)
    norm_s, _ = _normalise_with_index(span)
    if not norm_s:
        return None
    pos = norm_t.find(norm_s)
    if pos >= 0:
        return transcript[index[pos] : index[pos + len(norm_s) - 1] + 1]
    # Near-verbatim: the longest common block must cover most of the quote.
    m = SequenceMatcher(None, norm_t, norm_s, autojunk=False).find_longest_match(0, len(norm_t), 0, len(norm_s))
    if m.size >= min_ratio * len(norm_s):
        return transcript[index[m.a] : index[m.a + m.size - 1] + 1]
    return None


def _normalise_with_index(text: str) -> tuple[str, list[int]]:
    """Lower case, letters/digits/% only, single spaces; plus each output char's index in `text`."""
    out: list[str] = []
    index: list[int] = []
    for i, ch in enumerate(text):
        c = ch.lower()
        if c.isalnum() or c == "%":
            out.append(c)
            index.append(i)
        elif out and out[-1] != " ":
            out.append(" ")
            index.append(i)
    while out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


# --------------------------------------------------------------------------- offline fallback

def rule_based_star(transcript: str) -> StarScore:
    """Find each element from cue phrases; the sentence with the cue becomes the evidence."""
    sentences = split_sentences(transcript)
    used: set[int] = set()
    out: dict[str, StarElement] = {}
    for name in ELEMENTS:
        out[name] = StarElement(present=False)
        for i, sentence in enumerate(sentences):
            if i in used or not has_cue(sentence, name):
                continue
            used.add(i)
            words = len(sentence.split())
            strength = 1 + (words >= 8) + bool(re.search(r"\d|percent|%", sentence, re.I))
            out[name] = StarElement(present=True, evidence_span=sentence, strength=min(3, strength))
            break
    return StarScore(**out, source="rules")


def has_cue(sentence: str, element: str) -> bool:
    s = " " + re.sub(r"\s+", " ", sentence.lower()) + " "
    for cue in CUES[element]:
        if cue == "%":
            if "%" in s:
                return True
        elif re.search(r"(?<![a-z])" + re.escape(cue) + r"(?![a-z])", s):
            return True
    return False


def split_sentences(text: str) -> list[str]:
    """Sentences, or ~25-word chunks when speech-to-text produced no punctuation."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    out: list[str] = []
    for p in parts:
        words = p.split()
        if len(words) <= 40:
            out.append(p)
        else:
            out.extend(" ".join(words[i : i + 25]) for i in range(0, len(words), 25))
    return out


def star_score(star: StarScore) -> float:
    """0-100: total strength over the maximum (4 elements x 3)."""
    total = sum(getattr(star, name).strength for name in ELEMENTS)
    return round(100 * total / 12, 1)


def _empty(source: str) -> StarScore:
    return StarScore(**{name: StarElement(present=False) for name in ELEMENTS}, source=source)
