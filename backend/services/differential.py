"""Market-weighted skill gaps: which missing skills do the nearby jobs actually ask for?

    market_gaps(missing, jobs) -> list[MarketGap]   ("14 of 20 jobs ask for SQL")
    score_job(user_skills, job, distance_km)        per-job match for the map and the chatbot
"""
from __future__ import annotations

from backend.schemas import Job, JobMatch, MarketGap, Skill
from backend.services import matcher


def score_job(user_skills: list[Skill], job: Job, distance_km: float) -> JobMatch:
    """Match the user against one job's required skills."""
    result = matcher.match(user_skills, job.required_skills)
    return JobMatch(
        id=job.id,
        match_pct=result.match_pct,
        matched=[m.matched_to for m in result.matched],
        missing=[s.name for s in result.missing],
        distance_km=round(distance_km, 2),
    )


def market_gaps(missing: list[Skill], jobs: list[Job]) -> list[MarketGap]:
    """Rank missing skills by role weight, adjusted by how many of `jobs` require each one.

    priority = role weight * (0.5 + 0.5 * share of jobs requiring the skill), so the role's own
    weighting dominates and market demand reorders skills of similar weight.
    """
    total = len(jobs)
    counts = _demand(missing, jobs)
    gaps = []
    for skill in missing:
        n = counts[skill.name]
        demand = n / total if total else 0.0
        gaps.append(
            MarketGap(
                skill=skill.name,
                jobs_requiring=n,
                jobs_total=total,
                priority=round(skill.weight * (0.5 + 0.5 * demand), 3),
            )
        )
    return sorted(gaps, key=lambda g: (-g.priority, g.skill.lower()))


def _demand(missing: list[Skill], jobs: list[Job]) -> dict[str, int]:
    """How many jobs require each missing skill, by exact name or embedding similarity >= match threshold."""
    if not missing or not jobs:
        return {s.name: 0 for s in missing}

    job_skill_names = sorted({sk.name for job in jobs for sk in job.required_skills})
    names = [s.name for s in missing] + job_skill_names
    vectors = dict(zip(names, matcher.embed_cached(names)))

    def same(a: str, b: str) -> bool:
        return a.lower() == b.lower() or matcher.cosine(vectors[a], vectors[b]) >= matcher.MATCH_THRESHOLD

    return {
        skill.name: sum(1 for job in jobs if any(same(skill.name, sk.name) for sk in job.required_skills))
        for skill in missing
    }
