"""Jobs routes for the map: nearby listings scored against the profile, one listing by id.
Register with app.include_router(jobs.router)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.errors import HANDLED, http_error
from backend.schemas import Job
from backend.schemas.analyzer import JobNearby
from backend.services import differential, session
from backend.services.data import find_job, load_jobs
from backend.services.geo import nearby_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])

DEFAULT_RADIUS_KM = 25.0


@router.get("/nearby", response_model=list[JobNearby])
def get_nearby(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius: float = Query(default=DEFAULT_RADIUS_KM, gt=0, le=500),
    limit: int = Query(default=50, ge=1, le=200),
    min_match: float = Query(default=0, ge=0, le=100),
) -> list[JobNearby]:
    """Jobs within `radius` km, best match first; lat/lng default to the profile's location."""
    profile = session.get_profile()
    if not profile.skills:
        raise HTTPException(status_code=409, detail="Upload a CV first.")
    if (lat is None or lng is None) and profile.location is not None:
        lat, lng = profile.location.lat, profile.location.lng
    if lat is None or lng is None:
        raise HTTPException(status_code=422, detail="Pass lat and lng, or set a location on the profile first.")

    try:
        jobs = load_jobs()
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
            )
        )
    scored.sort(key=lambda m: (-m.match_pct, m.distance_km))
    return scored[:limit]


@router.get("/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    try:
        return find_job(job_id)
    except HANDLED as exc:
        raise http_error(exc) from exc
