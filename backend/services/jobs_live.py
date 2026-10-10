"""Real job postings for a role in a place, through the JSearch API (LinkedIn, Indeed, Glassdoor and
other boards, with apply links and coordinates). No listing shown on the map is generated.

    jobs_for(role, location) -> list[Job]      the postings the Career Map and the gap use
    search_jobs(role, place) -> list[Job]      one JSearch query, cached on disk

Set RAPIDAPI_KEY (free plan at rapidapi.com, API "JSearch" by OpenWeb Ninja). JOBS_SOURCE chooses the
source: "live" (the default), or "dataset" (data/jobs.json: the synthetic sample used by the tests and the
offline demo, every listing flagged synthetic=True). Without a key, job lookups raise JobsUnavailable and
the UI says what to configure; sample listings are never shown unless JOBS_SOURCE=dataset is set.

Required skills are read from each posting's text with the same role-vocabulary lexicon the CV extractor
uses, so a posting that says "SQL, Power BI and Excel" gets those three as core skills (weight 1).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from backend.schemas import Job, Location, Skill
from backend.services import geocode
from backend.services.data import DataError, RoleNotFound, find_role, load_jobs
from backend.services.data import find_job as find_dataset_job
from backend.services.extractor import lexicon_skills

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search-v2"  # v1 "/search" was retired in 2026
JSEARCH_HOST = "jsearch.p.rapidapi.com"
CACHE_PATH = Path(__file__).resolve().parents[1] / "cache" / "jobs_live.json"
CACHE_TTL_S = 12 * 3600  # JSearch's free plan is 200 requests/month: one query per role+place per half day
TIMEOUT = 20
PAGES_PER_CALL = 2  # num_pages: 10 postings per page, fetched in one HTTP call
MIN_NAMED_SKILLS = 3  # postings naming fewer skills than this are topped up with the role's core skills
TEXT_CHARS = 6000


class JobsUnavailable(RuntimeError):
    """No live source configured, or the live source refused the request."""


def source() -> str:
    """'live' when a JSearch key is set (or JOBS_SOURCE=live), else 'dataset' so the map is never empty.
    Dataset listings carry synthetic=True and the UI labels them as sample listings."""
    chosen = (os.getenv("JOBS_SOURCE") or "").strip().lower()
    if chosen in ("live", "dataset"):
        return chosen
    return "live" if os.getenv("RAPIDAPI_KEY") else "dataset"


def jobs_for(role: str | None, location: Location | None) -> list[Job]:
    """The postings to score for this user: real ones for `role` near `location`, or the dataset."""
    if source() == "dataset":
        return load_jobs()
    if not os.getenv("RAPIDAPI_KEY"):
        raise JobsUnavailable(
            "Live job search needs RAPIDAPI_KEY (JSearch on rapidapi.com) in .env, or JOBS_SOURCE=dataset for the sample data."
        )
    if not role:
        raise JobsUnavailable("Pick a target role to search real job postings.")
    place = place_name(location)
    if not place:
        raise JobsUnavailable("Enter a city or area to search real job postings.")
    return search_jobs(role, place, fallback=location)


def place_name(location: Location | None) -> str:
    """The place to search: the location's city, else a city name for its coordinates."""
    if location is None:
        return ""
    if location.city.strip():
        return location.city.strip()
    try:
        return geocode.reverse(location.lat, location.lng)
    except geocode.GeocodeError:
        return ""


def search_jobs(role: str, place: str, *, fallback: Location | None = None) -> list[Job]:
    """One JSearch query ("<role> in <place>"), converted to Job and cached for CACHE_TTL_S."""
    query = f"{role.strip()} in {place.strip()}"
    key = hashlib.sha256(query.lower().encode("utf-8")).hexdigest()[:24]
    cached = _cache_get(key)
    if cached is not None:
        return [Job.model_validate(j) for j in cached]

    rows = _fetch(query, _country(fallback))
    core = _role_core(role)
    jobs = [job for row in rows if (job := _job(row, fallback, core)) is not None]
    _cache_put(key, [j.model_dump(mode="json") for j in jobs])
    return jobs


def _country(location: Location | None) -> str | None:
    """ISO country code for the search location (JSearch filters by it), or None when unknown."""
    if location is None:
        return None
    try:
        return geocode.country_code(location.lat, location.lng) or None
    except geocode.GeocodeError:
        return None


def _fetch(query: str, country: str | None) -> list[dict[str, Any]]:
    headers = {"X-RapidAPI-Key": os.environ["RAPIDAPI_KEY"], "X-RapidAPI-Host": JSEARCH_HOST}
    params: dict[str, Any] = {"query": query, "page": 1, "num_pages": PAGES_PER_CALL}
    if country:
        params["country"] = country
    try:
        response = requests.get(JSEARCH_URL, params=params, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise JobsUnavailable(f"Job search failed: {exc}") from exc
    if response.status_code in (401, 403):
        raise JobsUnavailable("Job search refused the API key: check RAPIDAPI_KEY and that JSearch is subscribed.")
    if response.status_code == 429:
        raise JobsUnavailable("Job search quota exhausted for this month (JSearch free plan).")
    if not response.ok:
        raise JobsUnavailable(f"Job search failed with HTTP {response.status_code}.")
    try:
        data = response.json().get("data", [])
    except ValueError as exc:
        raise JobsUnavailable("Job search returned an unreadable reply.") from exc
    if isinstance(data, dict):  # search-v2: {"jobs": [...], "cursor": ...}
        data = data.get("jobs", [])
    return data if isinstance(data, list) else []


def _job(row: dict[str, Any], fallback: Location | None, role_core: list[Skill] = ()) -> Job | None:
    """A JSearch posting as a Job; None when it has no title, no employer or no usable position."""
    title = (row.get("job_title") or "").strip()
    company = (row.get("employer_name") or "").strip()
    if not title or not company:
        return None
    lat, lng = row.get("job_latitude"), row.get("job_longitude")
    if lat is None or lng is None:
        if fallback is None:
            return None
        lat, lng = fallback.lat, fallback.lng
    highlights = row.get("job_highlights") or {}
    parts = [row.get("job_description") or ""]
    if isinstance(highlights, dict):
        for section in ("Qualifications", "Responsibilities"):
            parts.extend(highlights.get(section) or [])
    elif isinstance(highlights, list):
        parts.extend(str(h) for h in highlights)
    text = "\n".join(p for p in parts if p)[:TEXT_CHARS]
    city = ", ".join(p for p in (row.get("job_city"), row.get("job_country")) if p) or (row.get("job_location") or "")
    return Job(
        id=f"js-{row.get('job_id') or hashlib.sha1((title + company).encode('utf-8')).hexdigest()[:12]}",
        company=company,
        title=title,
        city=city,
        lat=float(lat),
        lng=float(lng),
        requirements_text=text,
        required_skills=_required_skills(text, role_core),
        source_url=row.get("job_apply_link") or row.get("job_google_link"),
        source_name=(row.get("job_publisher") or "").strip(),
        posted_at=(row.get("job_posted_at") or "").strip(),
        synthetic=False,
    )


def _required_skills(text: str, role_core: list[Skill] = ()) -> list[Skill]:
    """Skills the posting names, from the role vocabulary and alias table (deterministic, no LLM).

    A posting that names fewer than MIN_NAMED_SKILLS is topped up with the target role's core skills as
    "preferred" requirements, so a two-line advert cannot score 100 % on one matching word.
    """
    found = [s.model_copy(update={"weight": 1.0, "requirement": "core", "sources": []}) for s in lexicon_skills(text)]
    if len(found) >= MIN_NAMED_SKILLS:
        return found
    present = {s.name.lower() for s in found}
    implied = [
        s.model_copy(update={"weight": 1.0, "requirement": "preferred", "sources": [], "evidence": []})
        for s in role_core
        if s.name.lower() not in present
    ]
    return [*found, *implied]


def _role_core(role: str) -> list[Skill]:
    """The target role's core skills (empty when the role or data is unknown)."""
    try:
        return [s for s in find_role(role).skills if s.requirement == "core"]
    except (DataError, RoleNotFound):
        return []


# --------------------------------------------------------------------------- disk cache

def _cache_get(key: str) -> list[dict[str, Any]] | None:
    try:
        store = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = store.get(key)
    if not entry or time.time() - entry.get("at", 0) > CACHE_TTL_S:
        return None
    return entry.get("jobs")


def _cache_put(key: str, jobs: list[dict[str, Any]]) -> None:
    try:
        store = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        store = {}
    store[key] = {"at": time.time(), "jobs": jobs}
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(store), encoding="utf-8")
    except OSError:
        pass


def find_job(job_id: str) -> Job:
    """A listing by id: a live posting seen in this process's cache, else the dataset (raises JobNotFound)."""
    if job_id.startswith("js-"):
        try:
            store = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            store = {}
        for entry in store.values():
            for raw in entry.get("jobs", []):
                if raw.get("id") == job_id:
                    return Job.model_validate(raw)
    return find_dataset_job(job_id)
