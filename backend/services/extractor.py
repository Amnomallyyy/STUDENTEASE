"""CV text -> skills[], projects[], experience[] (Module 2 input; reused by jobs and the analyzer).

Steps: strip personal details, ask the LLM for structured output, check the answer against the
CV text itself so a skill the CV never mentions cannot slip into the profile, then add any known skill
(role vocabulary + alias table) the CV names but the model skipped, so "DSA" on the CV is never "missing".
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from backend.llm_adapter import complete_json
from backend.schemas import ExtractedCV, Skill
from backend.services.data import DataError, load_roles
from backend.services.normalize import canonical, normalize_skills, variants

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "extract_skills.md"
MAX_CHARS = 15_000
REDACTED = "[redacted]"
LEXICON_CONFIDENCE = 0.8  # a skill the CV names literally but the model left out
EVIDENCE_CHARS = 160

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
    return _lexicon_pass(_verify(result, cleaned), cleaned)


@lru_cache(maxsize=1)
def _instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _mentions(haystack: str, name: str) -> bool:
    """True if the skill (or any alias of it) appears in the squashed, lower-case CV text."""
    return any(_pattern(variant).search(haystack) for variant in variants(name))


@lru_cache(maxsize=4096)
def _pattern(variant: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(variant.lower()) + r"(?![a-z0-9])")


@lru_cache(maxsize=1)
def _lexicon() -> tuple[Skill, ...]:
    """Every distinct skill any role asks for. Names of one or two letters ("C", "R", "Go") are left out:
    their word boundaries are unreliable in prose ("C" would match inside "C++")."""
    try:
        roles = load_roles()
    except DataError:
        return ()
    seen: dict[str, Skill] = {}
    for role in roles:
        for skill in role.skills:
            key = canonical(skill.name).lower()
            if key in seen or (len(skill.name) <= 2 and skill.name.isalpha()):
                continue
            seen[key] = Skill(name=canonical(skill.name), category=skill.category)
    return tuple(seen.values())


def lexicon_skills(text: str, *, exclude: set[str] | None = None) -> list[Skill]:
    """Known skills (role vocabulary + alias table) that `text` names, each quoting the line that names it.

    Deterministic and model-free: used as the CV extractor's safety net and to read the requirements
    out of real job postings. `exclude` holds lower-case canonical names to skip.
    """
    present = set(exclude or ())
    lines = [line for line in text.splitlines() if line.strip()]
    found: list[Skill] = []
    for entry in _lexicon():
        if entry.name.lower() in present:
            continue
        quote = next(
            (line.strip() for line in lines if any(_pattern(v).search(_squash(line)) for v in variants(entry.name))),
            None,
        )
        if quote is None:
            continue
        present.add(entry.name.lower())
        found.append(
            entry.model_copy(
                update={"evidence": [quote[:EVIDENCE_CHARS]], "sources": ["cv"], "confidence": LEXICON_CONFIDENCE}
            )
        )
    return found


def _lexicon_pass(result: ExtractedCV, cv_text: str) -> ExtractedCV:
    """Add known skills the CV names (by any alias) that the model's answer does not contain.

    The quote is the CV line that names the skill, so the Analyzer can still verify it; confidence is
    LEXICON_CONFIDENCE rather than 1.0 because no model judged the context.
    """
    added = lexicon_skills(cv_text, exclude={canonical(s.name).lower() for s in result.skills})
    if added:
        result.skills = normalize_skills([*result.skills, *added])
    return result


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
