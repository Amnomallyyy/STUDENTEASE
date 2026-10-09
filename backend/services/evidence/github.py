"""GitHub evidence through the official REST API only (no scraping).

    get_github(username)              -> GitHubEvidence: the demo cache if it has the user, else the API
    fetch_github(username, session=)  -> GitHubEvidence from api.github.com (at most 30 repos, forks skipped)
    load_cached(username, path=None)  -> GitHubEvidence | None from demo/cached_responses.json
    skills_from_github(evidence)      -> list[Skill]   one per language (share as confidence) and topic
    projects_from_github(evidence)    -> list[Project]

Env: GITHUB_TOKEN (optional bearer token, raises the rate limit), GITHUB_CACHE_PATH (cache file override).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field, ValidationError

from backend.schemas import Project, Skill, SkillCategory
from backend.services.normalize import canonical, normalize_skills

API = "https://api.github.com"
TIMEOUT = 15
MAX_REPOS = 30
README_CHARS = 2000
TOPIC_CONFIDENCE = 0.6
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[3] / "demo" / "cached_responses.json"

_LINK_LAST = re.compile(r'[?&]page=(\d+)[^>]*>;\s*rel="last"')


class GitHubError(RuntimeError):
    """Rate limit, network failure or a 5xx from GitHub."""


class GitHubUserNotFound(LookupError):
    pass


class GitHubRepo(BaseModel):
    name: str
    description: str = ""
    url: str = ""
    languages: dict[str, int] = Field(default_factory=dict, description="Language -> bytes of code.")
    topics: list[str] = Field(default_factory=list)
    readme: str = Field(default="", description=f"First {README_CHARS} characters, '' when absent.")
    commit_count: int = Field(default=0, ge=0)
    pushed_at: str = ""


class GitHubEvidence(BaseModel):
    username: str
    repos: list[GitHubRepo] = Field(default_factory=list)
    language_share: dict[str, float] = Field(
        default_factory=dict, description="Share (0-1) of all code bytes across the repos, per language."
    )


# --------------------------------------------------------------------------- cache

def cache_path(path: str | Path | None = None) -> Path:
    return Path(path or os.getenv("GITHUB_CACHE_PATH", str(DEFAULT_CACHE_PATH)))


def load_cached(username: str, path: str | Path | None = None) -> GitHubEvidence | None:
    """The recorded evidence for `username` (case-insensitive), or None when the file or user is absent."""
    file = cache_path(path)
    if not file.is_file():
        return None
    try:
        users = json.loads(file.read_text(encoding="utf-8")).get("github") or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    wanted = username.strip().lower()
    for name, raw in users.items():
        if name.lower() == wanted:
            try:
                return GitHubEvidence.model_validate(raw)
            except ValidationError:
                return None
    return None


def get_github(username: str) -> GitHubEvidence:
    """Cached evidence when the demo file has the user, otherwise a live fetch."""
    return load_cached(username) or fetch_github(username)


# --------------------------------------------------------------------------- REST client

def fetch_github(username: str, *, session: Any | None = None) -> GitHubEvidence:
    """Fetch the user's 30 most recently pushed non-fork repos with languages, topics, README and commit count.

    `session` only needs a `get(url, headers=, params=, timeout=)` method, so tests can pass a fake.
    """
    username = username.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", username):
        raise GitHubUserNotFound(f"'{username}' is not a valid GitHub username.")
    http = session or requests.Session()

    response = _get(http, f"{API}/users/{username}/repos", params={"per_page": MAX_REPOS, "sort": "pushed"})
    if response.status_code == 404:
        raise GitHubUserNotFound(f"GitHub user '{username}' not found.")
    _check(response)
    raw_repos = response.json()
    if not isinstance(raw_repos, list):
        raise GitHubError("Unexpected reply from GitHub when listing repositories.")

    repos = [_repo(http, item) for item in raw_repos[:MAX_REPOS] if not item.get("fork")]
    return GitHubEvidence(username=username, repos=repos, language_share=_language_share(repos))


def _repo(http: Any, item: dict[str, Any]) -> GitHubRepo:
    owner = (item.get("owner") or {}).get("login", "")
    name = item.get("name", "")
    base = f"{API}/repos/{owner}/{name}"

    languages = _get(http, f"{base}/languages")
    _check(languages)
    lang_bytes = languages.json() if languages.status_code == 200 else {}

    readme = _get(http, f"{base}/readme", accept="application/vnd.github.raw+json")
    readme_text = "" if readme.status_code == 404 else (_check(readme).text or "")

    return GitHubRepo(
        name=name,
        description=item.get("description") or "",
        url=item.get("html_url") or "",
        languages={k: int(v) for k, v in lang_bytes.items()} if isinstance(lang_bytes, dict) else {},
        topics=[t for t in (item.get("topics") or []) if isinstance(t, str)],
        readme=readme_text[:README_CHARS],
        commit_count=_commit_count(http, base),
        pushed_at=item.get("pushed_at") or "",
    )


def _commit_count(http: Any, base: str) -> int:
    """Page count from the Link header of a per_page=1 request; an empty repo answers 409 and counts as 0."""
    response = _get(http, f"{base}/commits", params={"per_page": 1})
    if response.status_code in (404, 409):
        return 0
    _check(response)
    match = _LINK_LAST.search(response.headers.get("Link", "") or "")
    if match:
        return int(match.group(1))
    items = response.json()
    return len(items) if isinstance(items, list) else 0


def _language_share(repos: list[GitHubRepo]) -> dict[str, float]:
    totals: dict[str, int] = {}
    for repo in repos:
        for language, size in repo.languages.items():
            totals[language] = totals.get(language, 0) + size
    grand = sum(totals.values())
    if not grand:
        return {}
    return {language: round(size / grand, 4) for language, size in sorted(totals.items(), key=lambda kv: -kv[1])}


def _headers(accept: str) -> dict[str, str]:
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(http: Any, url: str, *, params: dict[str, Any] | None = None, accept: str = "application/vnd.github+json"):
    try:
        return http.get(url, headers=_headers(accept), params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise GitHubError(f"Could not reach GitHub: {exc}") from exc


def _check(response):
    """Turn rate limits and server errors into GitHubError; return the response otherwise."""
    status = response.status_code
    if status in (403, 429):
        remaining = response.headers.get("X-RateLimit-Remaining")
        detail = "rate limit reached; set GITHUB_TOKEN" if remaining == "0" or status == 429 else "access forbidden"
        raise GitHubError(f"GitHub {detail} (HTTP {status}).")
    if status >= 500:
        raise GitHubError(f"GitHub is unavailable (HTTP {status}).")
    if status >= 400 and status != 404:
        raise GitHubError(f"GitHub request failed (HTTP {status}).")
    return response


# --------------------------------------------------------------------------- evidence -> profile objects

def skills_from_github(evidence: GitHubEvidence) -> list[Skill]:
    """Languages become `language` skills whose confidence is their share of the code; topics become tools."""
    total = sum(size for repo in evidence.repos for size in repo.languages.values())
    skills: list[Skill] = []
    for language, share in evidence.language_share.items():
        quotes = [
            f"{repo.name}: {round(100 * repo.languages[language] / total)}% of code"
            for repo in evidence.repos
            if language in repo.languages and total
        ]
        skills.append(
            Skill(
                name=canonical(language),
                category=SkillCategory.language,
                evidence=quotes,
                sources=["github"],
                confidence=round(min(1.0, share), 4),
            )
        )
    for repo in evidence.repos:
        for topic in repo.topics:
            skills.append(
                Skill(
                    name=canonical(topic.replace("-", " ")),
                    category=SkillCategory.tool,
                    evidence=[f"{repo.name}: topic '{topic}'"],
                    sources=["github"],
                    confidence=TOPIC_CONFIDENCE,
                )
            )
    return normalize_skills(skills)


def projects_from_github(evidence: GitHubEvidence) -> list[Project]:
    projects = []
    for repo in evidence.repos:
        names = [canonical(language) for language in repo.languages] + [canonical(t.replace("-", " ")) for t in repo.topics]
        projects.append(
            Project(
                name=repo.name,
                description=repo.description or _first_line(repo.readme),
                skills=list(dict.fromkeys(names)),
                url=repo.url or None,
            )
        )
    return projects


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:200]
    return ""
