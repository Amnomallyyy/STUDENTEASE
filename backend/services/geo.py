"""Distance helpers for the nearby-jobs map. M5's jobs API can reuse nearby_jobs()."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from backend.schemas import Job

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    d_lat, d_lng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearby_jobs(
    jobs: list[Job],
    location: tuple[float, float] | None,
    radius_km: float,
    limit: int | None = None,
) -> list[tuple[Job, float]]:
    """Jobs within `radius_km` of `location`, closest first, as (job, distance_km) pairs.

    With no location the radius cannot be applied: every job is returned with distance 0.0.
    """
    if location is None:
        pairs = [(job, 0.0) for job in jobs]
    else:
        lat, lng = location
        pairs = [(job, haversine_km(lat, lng, job.lat, job.lng)) for job in jobs]
        pairs = sorted((p for p in pairs if p[1] <= radius_km), key=lambda p: p[1])
    return pairs[:limit] if limit is not None else pairs
