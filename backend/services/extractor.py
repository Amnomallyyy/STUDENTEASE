"""CV text -> skills[], projects[], experience[] (Module 2 input; reused by jobs and the analyzer).

Steps: strip personal details, ask the LLM for structured output, then check the answer against the
CV text itself so a skill the CV never mentions cannot slip into the profile.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from backend.llm_adapter import complete_json
from backend.schemas import ExtractedCV
from backend.services.normalize import canonical, normalize_skills, variants

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "extract_skills.md"
MAX_CHARS = 15_000
REDACTED = "[redacted]"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_OR_ID = re.compile(r"(?<![\w/])\+?\d[\d \t().-]{7,}\d(?![\w/])")
_DOB_LINE = re.compile(r"(?im)^[ \t]*(?:date of birth|d\.?o\.?b\.?|born)\b.*$")
_ADDRESS_LINE = re.compile(r"(?im)^[ \t]*(?:address|residence|home address)\b.*$")


def redact_pii(text: str) -> str:
    """Remove email, phone / ID numbers, date of birth and address lines before any LLM call.

    This is a best-effort filter for the demo, not a guarantee: a free-text address that is not on
    a line starting with "Address" will not be caught.
    """
    text = _EMAIL.sub(REDACTED, text)
    text = _DOB_LINE.sub(REDACTED, text)
    text = _ADDRESS_LINE.sub(REDACTED, text)
    # Phone and national-ID numbers have 9+ digits; date ranges like "2019 - 2023" have 8.
    return _PHONE_OR_ID.sub(lambda m: REDACTED if sum(c.isdigit() for c in m.group()) >= 9 else m.group(), text)


def extract_from_text(cv_text: str) -> ExtractedCV:
    """Extract structured career data from the plain text of a CV."""
    cleaned = redact_pii(cv_text).replace("</cv>", "")[:MAX_CHARS]
    if not cleaned.strip():
        return ExtractedCV()
    prompt = f"{_instructions()}\n\n<cv>\n{cleaned}\n</cv>"
    result = complete_json(prompt, ExtractedCV, max_tokens=3000)
    return _verify(result, cleaned)


@lru_cache(maxsize=1)
def _instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _mentions(haystack: str, name: str) -> bool:
    """True if the skill (or any alias of it) appears in the squashed, lower-case CV text."""
    for variant in variants(name):
        pattern = r"(?<![a-z0-9])" + re.escape(variant.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, haystack):
            return True
    return False


def _verify(result: ExtractedCV, cv_text: str) -> ExtractedCV:
    """Drop skills the CV does not support, keep only quotes that really occur, normalise names."""
    haystack = _squash(cv_text)
    kept = []
    for skill in result.skills:
        quotes = [q for q in skill.evidence if _squash(q) and _squash(q) in haystack]
        if not quotes and not _mentions(haystack, skill.name):
            continue
        kept.append(skill.model_copy(update={"name": canonical(skill.name), "evidence": quotes, "sources": ["cv"]}))
    result.skills = normalize_skills(kept)
    for item in (*result.projects, *result.experience):
        item.skills = list(dict.fromkeys(canonical(s) for s in item.skills))
    return result
