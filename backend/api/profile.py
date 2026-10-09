"""Profile routes. Register with app.include_router(profile.router) in backend/main.py (M5)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.api.errors import HANDLED, http_error
from backend.schemas import Location, Profile, ProfilePatch, UserMode
from backend.services import career, session
from backend.services.cv_text import CVTextError, extract_text
from backend.services.data import DataError, RoleNotFound
from backend.services.extractor import extract_from_text

router = APIRouter(prefix="/profile", tags=["profile"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.get("", response_model=Profile)
def get_profile() -> Profile:
    return session.get_profile()


@router.post("/cv", response_model=Profile)
def upload_cv(
    file: UploadFile = File(...),
    target_role: str | None = Form(default=None),
    mode: UserMode = Form(default=UserMode.student),
    lat: float | None = Form(default=None, ge=-90, le=90),
    lng: float | None = Form(default=None, ge=-180, le=180),
    city: str = Form(default=""),
) -> Profile:
    """Read the CV, extract skills, and (if a target role is given) compute the first gap."""
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 5 MB.")
    try:
        text = extract_text(file.filename or "", content)
    except CVTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        extracted = extract_from_text(text)
    except HANDLED as exc:
        raise http_error(exc) from exc

    profile = Profile(
        mode=mode,
        target_role=target_role or None,
        location=Location(lat=lat, lng=lng, city=city) if lat is not None and lng is not None else None,
        skills=extracted.skills,
        projects=extracted.projects,
        experience=extracted.experience,
    )
    if profile.target_role:
        try:
            gap = career.compute_gap(profile.skills, profile.target_role, profile.location)
        except (RoleNotFound, DataError):
            # The CV was read fine; GET /career/gap reports the data or role problem explicitly.
            gap = None
        if gap:
            profile.target_role = gap.role
            profile.gap, profile.market_gaps, profile.jobs_nearby = gap.match, gap.market_gaps, gap.jobs_nearby
    session.set_profile(profile)
    return profile


@router.patch("", response_model=Profile)
def patch_profile(patch: ProfilePatch) -> Profile:
    changes = {name: value for name in ("mode", "target_role", "location") if (value := getattr(patch, name)) is not None}
    return session.update_profile(**changes)


@router.delete("", status_code=204)
def delete_profile() -> None:
    """'Delete my data': clears the server-side profile (the browser clears its own copy)."""
    session.reset_profile()
