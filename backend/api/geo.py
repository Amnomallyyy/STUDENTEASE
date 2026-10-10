"""Place lookup for the job map: GET /geo/place?q=Gulberg, Lahore -> coordinates and a display name.
Register with app.include_router(geo.router). Backed by services/geocode.py (Nominatim, cached)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.services import geocode
from backend.services.geocode import Place

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/place", response_model=Place)
def get_place(q: str = Query(min_length=2, max_length=120, description="City or area, e.g. 'Lahore' or 'DHA, Karachi'.")) -> Place:
    """The best match for a free-text place; 404 when nothing matches, 503 when the lookup service is down."""
    try:
        place = geocode.geocode(q)
    except geocode.GeocodeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if place is None:
        raise HTTPException(status_code=404, detail=f"No place found for '{q}'. Try a city name.")
    return place
