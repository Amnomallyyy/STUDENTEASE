"""Polite Nominatim geocoder with an on-disk cache, used by build_jobs.py --geocode only.

    geocode("Clifton, Karachi, Pakistan") -> (lat, lng) or None

Nominatim's usage policy asks for a descriptive User-Agent and at most one request per second, so
calls are spaced MIN_INTERVAL seconds apart and every answer (including misses) is cached in
data/geocode_cache.json. The default dataset build never calls this module.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "CareerLens-dataset-builder/0.1 (AICON'26 hackathon project; one-off area lookup for synthetic jobs)"
MIN_INTERVAL = 1.1  # seconds between requests
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "data" / "geocode_cache.json"

_last_call = 0.0


def geocode(query: str, cache_path: Path = DEFAULT_CACHE) -> tuple[float, float] | None:
    """Look a place name up on Nominatim, returning (lat, lng) or None when nothing matches."""
    cache = _load(cache_path)
    key = query.strip().lower()
    if key in cache:
        hit = cache[key]
        return (hit["lat"], hit["lng"]) if hit else None

    result = _fetch(query)
    cache[key] = {"lat": result[0], "lng": result[1]} if result else None
    _save(cache_path, cache)
    return result


def _fetch(query: str) -> tuple[float, float] | None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1, "countrycodes": "pk"})
    request = urllib.request.Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    _last_call = time.monotonic()
    if not payload:
        return None
    return float(payload[0]["lat"]), float(payload[0]["lon"])


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}  # a broken cache is just a cold cache


def _save(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
