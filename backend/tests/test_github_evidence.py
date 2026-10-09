"""GitHub client tests against a fake requests.Session, plus the demo cache. Nothing touches the network."""
import json

import pytest
import requests

from backend.services.evidence import github
from backend.services.evidence.github import GitHubError, GitHubEvidence, GitHubRepo, GitHubUserNotFound

OWNER = {"login": "demo"}
REPOS = [
    {
        "name": "sales-dashboard",
        "owner": OWNER,
        "description": "Sales KPIs",
        "html_url": "https://github.com/demo/sales-dashboard",
        "topics": ["pandas", "numpy"],
        "pushed_at": "2026-09-01T00:00:00Z",
        "fork": False,
    },
    {"name": "forked-thing", "owner": OWNER, "fork": True},
    {"name": "weather-dashboard", "owner": OWNER, "html_url": "https://github.com/demo/weather-dashboard", "fork": False},
]


class FakeResponse:
    def __init__(self, status_code, body=None, text="", headers=None):
        self.status_code, self._body, self.text, self.headers = status_code, body, text, headers or {}

    def json(self):
        return self._body


class FakeSession:
    """Answers the handful of GitHub endpoints the client uses; records every call."""

    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, headers, params, timeout))
        path = url.removeprefix(github.API)
        if path == "/users/demo/repos":
            return FakeResponse(200, REPOS)
        if path == "/users/nobody/repos":
            return FakeResponse(404, {"message": "Not Found"})
        if path == "/users/limited/repos":
            return FakeResponse(403, {"message": "rate limit"}, headers={"X-RateLimit-Remaining": "0"})
        if path == "/users/broken/repos":
            return FakeResponse(503)
        if path == "/repos/demo/sales-dashboard/languages":
            return FakeResponse(200, {"Python": 6000})
        if path == "/repos/demo/weather-dashboard/languages":
            return FakeResponse(200, {"JavaScript": 3500, "HTML": 500})
        if path == "/repos/demo/sales-dashboard/readme":
            return FakeResponse(200, text="# Sales dashboard\n" + "x" * 5000)
        if path == "/repos/demo/weather-dashboard/readme":
            return FakeResponse(404)
        if path == "/repos/demo/sales-dashboard/commits":
            link = '<https://api.github.com/x?per_page=1&page=2>; rel="next", <https://api.github.com/x?per_page=1&page=12>; rel="last"'
            return FakeResponse(200, [{"sha": "a"}], headers={"Link": link})
        if path == "/repos/demo/weather-dashboard/commits":
            return FakeResponse(200, [{"sha": "b"}])
        raise AssertionError(f"unexpected call {url}")


def test_fetch_builds_evidence_from_the_rest_api(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    http = FakeSession()

    evidence = github.fetch_github("demo", session=http)

    assert [r.name for r in evidence.repos] == ["sales-dashboard", "weather-dashboard"]  # fork skipped
    sales, weather = evidence.repos
    assert sales.commit_count == 12 and weather.commit_count == 1
    assert len(sales.readme) == github.README_CHARS and weather.readme == ""
    assert sales.topics == ["pandas", "numpy"] and weather.topics == []
    assert evidence.language_share == {"Python": 0.6, "JavaScript": 0.35, "HTML": 0.05}

    first_url, first_headers, first_params, timeout = http.calls[0]
    assert first_url.endswith("/users/demo/repos") and first_params == {"per_page": 30, "sort": "pushed"}
    assert first_headers["Accept"] == "application/vnd.github+json" and first_headers["Authorization"] == "Bearer t0ken"
    assert timeout == github.TIMEOUT
    readme_headers = next(h for u, h, _, _ in http.calls if u.endswith("/readme"))
    assert readme_headers["Accept"] == "application/vnd.github.raw+json"


def test_unknown_user_rate_limit_and_outage_map_to_the_two_errors():
    http = FakeSession()
    with pytest.raises(GitHubUserNotFound):
        github.fetch_github("nobody", session=http)
    with pytest.raises(GitHubError, match="rate limit"):
        github.fetch_github("limited", session=http)
    with pytest.raises(GitHubError, match="503"):
        github.fetch_github("broken", session=http)
    with pytest.raises(GitHubUserNotFound):
        github.fetch_github("not a user!", session=http)


def test_network_failure_is_a_github_error():
    class Down:
        def get(self, *args, **kwargs):
            raise requests.ConnectionError("no route")

    with pytest.raises(GitHubError, match="reach GitHub"):
        github.fetch_github("demo", session=Down())


def test_skills_and_projects_from_evidence():
    evidence = github.fetch_github("demo", session=FakeSession())

    skills = {s.name: s for s in github.skills_from_github(evidence)}
    assert skills["JavaScript"].confidence == 0.35
    assert skills["JavaScript"].evidence == ["weather-dashboard: 35% of code"]
    assert skills["JavaScript"].sources == ["github"]
    assert skills["pandas"].confidence == github.TOPIC_CONFIDENCE and skills["pandas"].category == "tool"

    projects = github.projects_from_github(evidence)
    assert [p.name for p in projects] == ["sales-dashboard", "weather-dashboard"]
    assert projects[0].skills == ["Python", "pandas", "numpy"] and projects[0].url.endswith("sales-dashboard")


def test_cache_lookup_is_case_insensitive_and_get_github_prefers_it(tmp_path, monkeypatch):
    evidence = GitHubEvidence(
        username="Demo", repos=[GitHubRepo(name="x", languages={"Python": 10})], language_share={"Python": 1.0}
    )
    path = tmp_path / "cached_responses.json"
    path.write_text(json.dumps({"github": {"Demo": evidence.model_dump()}, "llm": {}}), encoding="utf-8")

    assert github.load_cached("demo", path) == evidence
    assert github.load_cached("other", path) is None
    assert github.load_cached("demo", tmp_path / "missing.json") is None

    monkeypatch.setenv("GITHUB_CACHE_PATH", str(path))

    def no_network(username, **kwargs):
        raise AssertionError("cached users must not hit the API")

    monkeypatch.setattr(github, "fetch_github", no_network)
    assert github.get_github("DEMO") == evidence
