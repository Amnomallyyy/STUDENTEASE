"""Career map routes: gap, roadmap, adjacent roles. Register with app.include_router(career.router)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.errors import HANDLED, http_error
from backend.schemas import AdjacentRole, GapResponse, Location, Profile, Roadmap, Role
from backend.services import career, session
from backend.services.data import load_roles

router = APIRouter(prefix="/career", tags=["career"])


@router.get("/roles", response_model=list[Role])
def list_roles() -> list[Role]:
    """Every target role with its weighted skills, for the role picker and the keyword-vs-embedding toggle (M2)."""
    try:
        return load_roles()
    except HANDLED as exc:
        raise http_error(exc) from exc


def _ready_profile(role: str | None) -> tuple[Profile, str]:
    profile = session.get_profile()
    if not profile.skills:
        raise HTTPException(status_code=409, detail="Upload a CV first.")
    name = role or profile.target_role
    if not name:
        raise HTTPException(status_code=422, detail="Pass ?role=... or set a target role first.")
    return profile, name


@router.get("/gap", response_model=GapResponse)
def get_gap(
    role: str | None = None,
    radius_km: float = Query(default=career.DEFAULT_RADIUS_KM, gt=0, le=500),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
) -> GapResponse:
    profile, name = _ready_profile(role)
    location = profile.location
    if lat is not None and lng is not None:
        location = Location(lat=lat, lng=lng, city=location.city if location else "")
    try:
        gap = career.compute_gap(profile.skills, name, location, radius_km, evidenced=bool(profile.evidence_sources))
    except HANDLED as exc:
        raise http_error(exc) from exc
    session.update_profile(
        target_role=gap.role,
        location=location,
        gap=gap.match,
        market_gaps=gap.market_gaps,
        jobs_nearby=gap.jobs_nearby,
    )
    return gap


@router.get("/roadmap", response_model=Roadmap)
def get_roadmap(
    role: str | None = None,
    pinned_job_id: str | None = None,
    radius_km: float = Query(default=career.DEFAULT_RADIUS_KM, gt=0, le=500),
) -> Roadmap:
    profile, name = _ready_profile(role)
    try:
        roadmap = career.make_roadmap(profile, name, pinned_job_id, radius_km)
    except HANDLED as exc:
        raise http_error(exc) from exc
    session.update_profile(roadmap=roadmap)
    return roadmap


@router.get("/adjacent", response_model=list[AdjacentRole])
def get_adjacent(role: str | None = None, limit: int = 5) -> list[AdjacentRole]:
    profile, name = _ready_profile(role)
    try:
        return career.adjacent_roles(profile.skills, exclude_role=name, limit=max(1, min(limit, 20)))
    except HANDLED as exc:
        raise http_error(exc) from exc
