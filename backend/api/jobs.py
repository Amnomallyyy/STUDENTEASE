"""Jobs routes for the map: real postings for a role in a place, scored against the profile; one listing by id.
Register with app.include_router(jobs.router). Source selection lives in services/jobs_live.py."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.errors import HANDLED, http_error
from backend.schemas import Job, Location
from backend.schemas.analyzer import JobNearby
from backend.services import differential, jobs_live, session
from backend.services.geo import nearby_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])

DEFAULT_RADIUS_KM = 25.0


@router.get("/nearby", response_model=list[JobNearby])
def get_nearby(
    role: str | None = Query(default=None, description="Defaults to the profile's target role."),
    place: str | None = Query(default=None, description="City or area to search; defaults to the profile's location."),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius: float = Query(default=DEFAULT_RADIUS_KM, gt=0, le=500),
    limit: int = Query(default=50, ge=1, le=200),
    min_match: float = Query(default=0, ge=0, le=100),
) -> list[JobNearby]:
    """Postings for `role` in `place` within `radius` km of lat/lng, best match first.

    503 when no job source is configured (see RAPIDAPI_KEY / JOBS_SOURCE); the detail says what to set.
    """
    profile = session.get_profile()
    if not profile.skills:
        raise HTTPException(status_code=409, detail="Upload a CV first.")
    if (lat is None or lng is None) and profile.location is not None:
        lat, lng = profile.location.lat, profile.location.lng
    if lat is None or lng is None:
        raise HTTPException(status_code=422, detail="Pass lat and lng, or set a location on the profile first.")
    city = (place or "").strip() or (profile.location.city if profile.location else "")
    location = Location(lat=lat, lng=lng, city=city)

    try:
        jobs = jobs_live.jobs_for((role or profile.target_role or "").strip() or None, location)
    except jobs_live.JobsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HANDLED as exc:
        raise http_error(exc) from exc

    scored = []
    for job, distance in nearby_jobs(jobs, (lat, lng), radius):
        match = differential.score_job(profile.skills, job, distance)
        if match.match_pct < min_match:
            continue
        scored.append(
            JobNearby(
                **match.model_dump(),
                company=job.company,
                title=job.title,
                city=job.city,
                lat=job.lat,
                lng=job.lng,
                synthetic=job.synthetic,
                source_url=job.source_url,
                source_name=job.source_name,
                posted_at=job.posted_at,
            )
        )
    scored.sort(key=lambda m: (-m.match_pct, m.distance_km))
    return scored[:limit]


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    try:
        return jobs_live.find_job(job_id)
    except HANDLED as exc:
        raise http_error(exc) from exc
