"""Career map orchestration: role gap + nearby jobs + roadmap. Used by the career API, the upload flow
and the chatbot tools, so all three give the same numbers."""
from __future__ import annotations

from backend.schemas import AdjacentRole, GapResponse, Location, Profile, Roadmap, Skill
from backend.services import differential, matcher
from backend.services.data import (
    DataMissing,
    find_job,
    find_role,
    load_jobs,
    load_resources,
    load_roles,
)
from backend.services.geo import nearby_jobs
from backend.services.roadmap import build_roadmap

DEFAULT_RADIUS_KM = 25.0
MARKET_JOBS = 20  # the outline sizes the market sample as the 20 nearest jobs


def _coords(location: Location | None) -> tuple[float, float] | None:
    return (location.lat, location.lng) if location else None


def compute_gap(
    skills: list[Skill],
    role_name: str,
    location: Location | None,
    radius_km: float = DEFAULT_RADIUS_KM,
    *,
    evidenced: bool = False,
) -> GapResponse:
    """Match the user to a role, then rank the missing skills against the nearest jobs.

    If jobs.json does not exist yet, the role match still works and the job fields are empty.
    `evidenced=True` (the Analyzer has run) also fills match.evidenced_pct.
    """
    role = find_role(role_name)
    result = matcher.match(skills, role.skills, evidenced=evidenced)
    try:
        jobs = load_jobs()
    except DataMissing:
        jobs = []
    pairs = nearby_jobs(jobs, _coords(location), radius_km, limit=MARKET_JOBS)
    gaps = differential.market_gaps(result.missing, [job for job, _ in pairs])
    scored = sorted(
        (differential.score_job(skills, job, distance) for job, distance in pairs),
        key=lambda m: (-m.match_pct, m.distance_km),
    )
    return GapResponse(role=role.name, match=result, market_gaps=gaps, jobs_nearby=scored)


def adjacent_roles(skills: list[Skill], exclude_role: str | None = None, limit: int = 5) -> list[AdjacentRole]:
    """Other roles ranked by how well the user's skills already fit them."""
    excluded = exclude_role.strip().lower() if exclude_role else None
    ranked = [
        AdjacentRole(role=role.name, match_pct=matcher.match(skills, role.skills).match_pct)
        for role in load_roles()
        if excluded not in (role.name.lower(), role.id.lower())
    ]
    return sorted(ranked, key=lambda r: (-r.match_pct, r.role))[:limit]


def make_roadmap(
    profile: Profile, role_name: str, pinned_job_id: str | None = None, radius_km: float = DEFAULT_RADIUS_KM
) -> Roadmap:
    """Build the 4-week plan; pinning a job moves that job's missing skills to the front."""
    gap = compute_gap(profile.skills, role_name, profile.location, radius_km)
    pinned_job = find_job(pinned_job_id) if pinned_job_id else None
    pinned_missing = (
        [s.name for s in matcher.match(profile.skills, pinned_job.required_skills).missing] if pinned_job else []
    )
    try:
        resources = load_resources()
    except DataMissing:
        resources = {}
    return build_roadmap(
        gap.market_gaps, resources, role=gap.role, pinned_job=pinned_job, pinned_missing=pinned_missing
    )
