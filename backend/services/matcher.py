"""Embedding skill matcher, reused by career gap, nearby jobs, the analyzer and interview relevance.

    match(user_skills, target_skills) -> MatchResult

Each target skill is compared with every user skill by cosine similarity:
    >= 0.80        matched
    0.65 - 0.80    partial
    below 0.65     missing
Match % is the weight of matched target skills over the total target weight. Partial matches are
shown to the user but earn no credit, which keeps the number easy to explain to judges.

Embeddings are cached in memory and on disk (backend/cache/embeddings.json) so repeated matching,
for example against 20 nearby jobs, only embeds each skill name once.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from backend.llm_adapter import embed
from backend.schemas import MatchResult, Skill, SkillMatch

MATCH_THRESHOLD = 0.80
PARTIAL_THRESHOLD = 0.65

CACHE_PATH: Path | None = Path(__file__).resolve().parents[1] / "cache" / "embeddings.json"
_memory: dict[str, list[float]] | None = None


def match(
    user_skills: list[Skill],
    target_skills: list[Skill],
    *,
    match_threshold: float = MATCH_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
) -> MatchResult:
    """Score a user's skills against the skills a role or job requires."""
    if partial_threshold > match_threshold:
        raise ValueError("partial_threshold must not exceed match_threshold")
    if not target_skills:
        return MatchResult(match_pct=0.0)

    user_by_name = {s.name.lower(): s for s in user_skills}
    best: dict[str, tuple[Skill, float]] = {}

    # Exact name matches need no embedding.
    pending: list[Skill] = []
    for target in target_skills:
        exact = user_by_name.get(target.name.lower())
        if exact is not None:
            best[target.name.lower()] = (exact, 1.0)
        else:
            pending.append(target)

    if pending and user_skills:
        vectors = embed_cached([s.name for s in user_skills] + [t.name for t in pending])
        user_vecs, target_vecs = vectors[: len(user_skills)], vectors[len(user_skills):]
        for target, t_vec in zip(pending, target_vecs):
            scores = [cosine(u_vec, t_vec) for u_vec in user_vecs]
            top = max(range(len(scores)), key=scores.__getitem__)
            best[target.name.lower()] = (user_skills[top], scores[top])

    matched: list[SkillMatch] = []
    partial: list[SkillMatch] = []
    missing: list[Skill] = []
    gained = 0.0
    for target in target_skills:
        found = best.get(target.name.lower())
        if found is not None and found[1] >= match_threshold:
            matched.append(_pair(found, target))
            gained += target.weight
        elif found is not None and found[1] >= partial_threshold:
            partial.append(_pair(found, target))
        else:
            missing.append(target)

    total = sum(t.weight for t in target_skills)
    pct = 100.0 * gained / total if total > 0 else 100.0 * len(matched) / len(target_skills)
    return MatchResult(match_pct=round(pct, 1), matched=matched, partial=partial, missing=missing)


def _pair(found: tuple[Skill, float], target: Skill) -> SkillMatch:
    user_skill, score = found
    return SkillMatch(name=user_skill.name, matched_to=target.name, similarity=round(max(0.0, min(1.0, score)), 3))


def cosine(a: list[float], b: list[float]) -> float:
    # embed() returns unit vectors, so the dot product is the cosine similarity.
    return sum(x * y for x, y in zip(a, b))


# --------------------------------------------------------------------------- embedding cache

def embed_cached(texts: list[str]) -> list[list[float]]:
    """Embed skill names, calling the model only for names not seen before."""
    store = _load_cache()
    missing = [t for t in dict.fromkeys(texts) if _key(t) not in store]
    if missing:
        for text, vec in zip(missing, embed(missing)):
            store[_key(text)] = [round(x, 5) for x in vec]
        _save_cache(store)
    return [store[_key(t)] for t in texts]


def _model_id() -> str:
    provider = os.getenv("EMBED_PROVIDER", "local").lower()
    model = os.getenv("OPENAI_EMBED_MODEL", "default") if provider == "openai" else os.getenv("EMBED_MODEL", "default")
    return f"{provider}:{model}"


def _key(text: str) -> str:
    return f"{_model_id()}|{text.strip().lower()}"


def _load_cache() -> dict[str, list[float]]:
    global _memory
    if _memory is None:
        _memory = {}
        if CACHE_PATH is not None and CACHE_PATH.is_file():
            try:
                _memory = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                _memory = {}  # a bad cache file is just a cold cache
    return _memory


def _save_cache(store: dict[str, list[float]]) -> None:
    if CACHE_PATH is None:
        return
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(store, separators=(",", ":")), encoding="utf-8")
    except OSError:
        pass  # the cache is an optimisation; never fail a request over it
