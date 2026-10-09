"""Skill-name normalisation: "JS" -> "JavaScript", and merging duplicates.

Aliases come from data/skill_aliases.json (owned by M5) layered over a small built-in set, so the
pipeline works before that file exists. The file may be either {"alias": "Canonical"} or
{"Canonical": ["alias", ...]}. Set SKILL_ALIASES_PATH to point somewhere else.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

from backend.schemas import Skill

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "skill_aliases.json"

_BUILTIN_ALIASES: dict[str, str] = {
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "python3": "Python",
    "reactjs": "React",
    "react.js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "tf": "TensorFlow",
    "k8s": "Kubernetes",
    "ms excel": "Excel",
    "microsoft excel": "Excel",
    "powerbi": "Power BI",
    "ms power bi": "Power BI",
    "c sharp": "C#",
    "golang": "Go",
}


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


@lru_cache(maxsize=1)
def _aliases() -> dict[str, str]:
    table = dict(_BUILTIN_ALIASES)
    path = Path(os.getenv("SKILL_ALIASES_PATH", str(_DEFAULT_PATH)))
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for left, right in data.items():
            if isinstance(right, list):  # {"Canonical": ["alias", ...]}
                for alias in right:
                    table[_key(alias)] = left
            else:  # {"alias": "Canonical"}
                table[_key(left)] = right
    for canonical_name in set(table.values()):
        table.setdefault(_key(canonical_name), canonical_name)
    return table


def reload_aliases() -> None:
    """Drop the cached alias table (used by tests and after M5 updates the file)."""
    _aliases.cache_clear()


def canonical(name: str) -> str:
    """Return the canonical spelling of a skill name, or the cleaned input if it is unknown."""
    cleaned = re.sub(r"\s+", " ", name.strip())
    return _aliases().get(_key(cleaned), cleaned)


def variants(name: str) -> set[str]:
    """Every spelling that maps to this skill (canonical name plus aliases), for text searches."""
    target = canonical(name)
    found = {target, name.strip()}
    found.update(alias for alias, value in _aliases().items() if value == target)
    return {v for v in found if v}


def normalize_skills(skills: list[Skill]) -> list[Skill]:
    """Canonicalise names and merge duplicates, unioning evidence and sources."""
    merged: dict[str, Skill] = {}
    for skill in skills:
        name = canonical(skill.name)
        current = skill.model_copy(update={"name": name})
        key = name.lower()
        if key not in merged:
            merged[key] = current
            continue
        base = merged[key]
        base.evidence = list(dict.fromkeys(base.evidence + current.evidence))
        base.sources = list(dict.fromkeys(base.sources + current.sources))
        base.confidence = max(base.confidence, current.confidence)
        base.weight = max(base.weight, current.weight)
        years = [y for y in (base.years, current.years) if y is not None]
        base.years = max(years) if years else None
        if current.requirement == "core":
            base.requirement = "core"
    return list(merged.values())
