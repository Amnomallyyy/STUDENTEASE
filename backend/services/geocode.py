"""Place name <-> coordinates through OpenStreetMap's Nominatim (free, no key), with an on-disk cache.

    geocode("Gulberg, Lahore")  -> Place(lat, lng, name) or None
    reverse(24.86, 67.0)        -> "Karachi" (city-level name) or ""
    country_code(24.86, 67.0)   -> "pk" or ""

Nominatim's policy asks for a descriptive User-Agent and at most one request per second, so calls are
spaced out and every answer (including misses) is cached in backend/cache/geocode.json.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field

NOMINATIM = "https://nominatim.openstreetmap.org"
USER_AGENT = "CareerLens/0.1 (AICON'26 hackathon project; place lookup for the job map)"
MIN_INTERVAL = 1.1  # seconds between requests
CACHE_PATH = Path(__file__).resolve().parents[1] / "cache" / "geocode.json"
TIMEOUT = 10


class Place(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    name: str = Field(description="Display name, e.g. 'Lahore, Punjab, Pakistan'.")
    city: str = Field(default="", description="City-level name when Nominatim reports one.")


class GeocodeError(RuntimeError):
    """Nominatim unreachable or refusing the request."""


_lock = threading.Lock()
_last_call = 0.0
_cache: dict[str, Any] | None = None


def geocode(query: str) -> Place | None:
    """The best match for a free-text place, or None when nothing matches."""
    key = "q:" + query.strip().lower()
    if not key[2:]:
        return None
    hit = _cached(key)
    if hit is not None:
        return Place(**hit) if hit else None
    rows = _get("/search", {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1})
    place = _place(rows[0]) if rows else None
    _store(key, place.model_dump() if place else {})
    return place


def reverse(lat: float, lng: float) -> str:
    """A city-level name for coordinates (empty when unknown), for "use my location" job searches."""
    key = f"r:{lat:.3f},{lng:.3f}"
    hit = _cached(key)
    if hit is not None:
        return hit.get("city", "")
    row = _get("/reverse", {"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 10, "addressdetails": 1})
    city = _city(row.get("address", {})) if isinstance(row, dict) else ""
    _store(key, {"city": city})
    return city


def country_code(lat: float, lng: float) -> str:
    """ISO 3166-1 alpha-2 code (lower case) for coordinates, empty when unknown."""
    key = f"c:{lat:.2f},{lng:.2f}"
    hit = _cached(key)
    if hit is not None:
        return hit.get("country_code", "")
    row = _get("/reverse", {"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 3, "addressdetails": 1})
    code = str((row.get("address", {}) if isinstance(row, dict) else {}).get("country_code", "")).lower()
    _store(key, {"country_code": code})
    return code


def _place(row: dict[str, Any]) -> Place:
    address = row.get("address", {})
    return Place(lat=float(row["lat"]), lng=float(row["lon"]), name=row.get("display_name", ""), city=_city(address))


def _city(address: dict[str, Any]) -> str:
    for field in ("city", "town", "municipality", "county", "state_district", "state"):
        if address.get(field):
            return str(address[field])
    return ""


def _get(path: str, params: dict[str, Any]) -> Any:
    global _last_call
    with _lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            response = requests.get(f"{NOMINATIM}{path}", params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GeocodeError(f"Place lookup failed: {exc}") from exc
        finally:
            _last_call = time.monotonic()
    return data


def _load() -> dict[str, Any]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _cached(key: str) -> Any:
    return _load().get(key)


def _store(key: str, value: Any) -> None:
    cache = _load()
    cache[key] = value
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    except OSError:
        pass
