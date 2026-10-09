"""Analyzer API tests with GitHub, the LLM and the embedding model all faked."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import analyzer as analyzer_api  # noqa: E402
from backend.llm_adapter import LLMError  # noqa: E402
from backend.schemas import ExtractedCV, Profile, Skill, SkillCategory  # noqa: E402
from backend.services import matcher, session  # noqa: E402
from backend.services.evidence import anomalies, linkedin  # noqa: E402
from backend.services.evidence.github import GitHubError, GitHubEvidence, GitHubRepo, GitHubUserNotFound  # noqa: E402

BASIS = ["python", "docker", "javascript", "excel"]
VECTORS = {name: [1.0 if d == name else 0.0 for d in BASIS] for name in BASIS}

GITHUB = GitHubEvidence(
    username="demo",
    repos=[
        GitHubRepo(name="sales-dashboard", languages={"Python": 6500}, readme="# Sales", commit_count=12),
        GitHubRepo(name="weather-dashboard", languages={"JavaScript": 3500}, commit_count=8),
    ],
    language_share={"Python": 0.65, "JavaScript": 0.35},
)


def skill(name, evidence=None):
    return Skill(name=name, category=SkillCategory.tool, sources=["cv"], evidence=[name] if evidence is None else evidence)


@pytest.fixture
def client(monkeypatch):
    session.reset_profile()
    analyzer_api._reports.clear()
    analyzer_api._latest_id = None
    monkeypatch.setattr(matcher, "embed", lambda texts: [VECTORS[t.lower()] for t in texts])
    monkeypatch.setattr(analyzer_api, "get_github", lambda username: GITHUB)

    def offline(*args, **kwargs):
        raise LLMError("offline")

    monkeypatch.setattr(anomalies, "complete_json", offline)
    app = FastAPI()
    app.include_router(analyzer_api.router)
    yield TestClient(app)
    session.reset_profile()


def with_cv():
    session.set_profile(Profile(skills=[skill("Python"), skill("Docker", evidence=["Expert in Docker"]), skill("Excel")]))


def test_run_needs_a_cv_then_a_source(client):
    assert client.post("/analyzer/run", data={"github_username": "demo"}).status_code == 409
    with_cv()
    assert client.post("/analyzer/run", data={"github_username": "  "}).status_code == 422
    assert client.get("/analyzer/report").status_code == 404


def test_github_errors_become_404_and_502(client, monkeypatch):
    with_cv()

    def missing(username):
        raise GitHubUserNotFound(f"GitHub user '{username}' not found.")

    monkeypatch.setattr(analyzer_api, "get_github", missing)
    assert client.post("/analyzer/run", data={"github_username": "nobody"}).status_code == 404

    def limited(username):
        raise GitHubError("rate limit")

    monkeypatch.setattr(analyzer_api, "get_github", limited)
    assert client.post("/analyzer/run", data={"github_username": "demo"}).status_code == 502


def test_run_with_github_builds_a_report_and_updates_the_profile(client):
    with_cv()

    response = client.post("/analyzer/run", data={"github_username": "demo"})

    assert response.status_code == 200
    body = response.json()
    assert {(a["kind"], a["claim"]) for a in body["anomalies"]} == {
        ("overclaim", "Docker"),
        ("unsupported_claim", "Excel"),
        ("missed_strength", "JavaScript"),
    }
    assert all(a["suggested_fix"] for a in body["anomalies"])  # templated, the LLM is offline
    assert body["integrity_score"] == 33.3 and body["github_username"] == "demo"
    assert body["sources"] == {"cv": 3, "github": 2}
    assert {c["name"] for c in body["clusters"]} == {"Python", "Docker", "Excel", "JavaScript"}

    profile = session.get_profile()
    assert profile.integrity_score == 33.3 and len(profile.anomalies) == 3

    assert client.get("/analyzer/report").json()["report_id"] == body["report_id"]
    assert client.get("/analyzer/report", params={"report_id": body["report_id"]}).status_code == 200
    assert client.get("/analyzer/report", params={"report_id": "nope"}).status_code == 404


def test_run_with_linkedin_text_and_file(client, monkeypatch):
    with_cv()
    seen = []

    def fake_extract(text):
        seen.append(text)
        return ExtractedCV(skills=[Skill(name="Python", category=SkillCategory.tool)])

    monkeypatch.setattr(linkedin, "extract_from_text", fake_extract)

    body = client.post("/analyzer/run", data={"linkedin_text": "Skills: Python"}).json()
    assert body["sources"] == {"cv": 3, "linkedin": 1} and body["github_username"] is None
    assert body["integrity_score"] == 33.3
    assert {a["kind"] for a in body["anomalies"]} == {"overclaim", "unsupported_claim"}
    assert next(c for c in body["clusters"] if c["name"] == "Python")["sources"] == ["cv", "linkedin"]

    files = {"linkedin_export": ("export.txt", b"Skills: Python", "text/plain")}
    assert client.post("/analyzer/run", files=files).status_code == 200
    assert seen == ["Skills: Python", "Skills: Python"]

    files = {"linkedin_export": ("export.docx", b"xx", "application/octet-stream")}
    assert client.post("/analyzer/run", files=files).status_code == 422


def test_linkedin_extraction_failure_is_a_502(client, monkeypatch):
    with_cv()

    def down(text):
        raise LLMError("provider down")

    monkeypatch.setattr(linkedin, "extract_from_text", down)
    assert client.post("/analyzer/run", data={"linkedin_text": "Skills: Python"}).status_code == 502
