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
    # The evidence flows back into the shared profile: sources on CV skills, GitHub-only skills appended.
    assert [(s.name, s.sources) for s in profile.skills] == [
        ("Python", ["cv", "github"]),
        ("Docker", ["cv"]),
        ("Excel", ["cv"]),
        ("JavaScript", ["github"]),
    ]
    assert profile.evidence_sources == ["github"]
    assert body["target_role"] is None and body["match"] is None  # no target role set

    # A second run still treats only the CV's own claims as claims: JavaScript is not "unsupported".
    again = client.post("/analyzer/run", data={"github_username": "demo"}).json()
    assert {(a["kind"], a["claim"]) for a in again["anomalies"]} == {(a["kind"], a["claim"]) for a in body["anomalies"]}
    assert again["sources"] == {"cv": 3, "github": 2}
    assert [s.name for s in session.get_profile().skills] == ["Python", "Docker", "Excel", "JavaScript"]

    assert client.get("/analyzer/report").json()["report_id"] == again["report_id"]  # latest wins
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


def test_run_refreshes_the_target_role_gap_with_evidence(client, monkeypatch):
    from backend.schemas import GapResponse, Location, MatchResult, SkillMatch
    from backend.services import career

    session.set_profile(
        Profile(target_role="Data Analyst", location=Location(lat=24.86, lng=67.0, city="Karachi"), skills=[skill("Python"), skill("Excel")])
    )
    seen = {}

    def fake_gap(skills, role_name, location, radius_km=25.0, *, evidenced=False):
        seen.update(skills=[(s.name, s.sources) for s in skills], role=role_name, evidenced=evidenced)
        match = MatchResult(
            match_pct=50.0,
            evidenced_pct=25.0,
            matched=[SkillMatch(name="Python", matched_to="Python", similarity=1.0, sources=["cv", "github"])],
        )
        return GapResponse(role="Data Analyst", match=match)

    monkeypatch.setattr(career, "compute_gap", fake_gap)

    body = client.post("/analyzer/run", data={"github_username": "demo"}).json()

    assert seen == {
        "skills": [("Python", ["cv", "github"]), ("Excel", ["cv"]), ("JavaScript", ["github"])],
        "role": "Data Analyst",
        "evidenced": True,
    }
    assert body["target_role"] == "Data Analyst" and body["match"]["evidenced_pct"] == 25.0
    profile = session.get_profile()
    assert profile.gap.evidenced_pct == 25.0 and profile.gap.matched[0].sources == ["cv", "github"]


def test_only_substantial_github_languages_join_the_profile(client, monkeypatch):
    with_cv()
    small = GitHubEvidence(
        username="demo",
        repos=[GitHubRepo(name="weather-dashboard", languages={"Python": 9000, "JavaScript": 1000}, commit_count=8)],
        language_share={"Python": 0.9, "JavaScript": 0.1},
    )
    monkeypatch.setattr(analyzer_api, "get_github", lambda username: small)

    body = client.post("/analyzer/run", data={"github_username": "demo"}).json()

    assert body["sources"] == {"cv": 3, "github": 2}  # both languages sit on the evidence board
    assert [s.name for s in session.get_profile().skills] == ["Python", "Docker", "Excel"]  # 10% JavaScript stays out

    topic = Skill(name="weather", category=SkillCategory.tool, sources=["github"], confidence=0.6)
    strong = Skill(name="Go", category=SkillCategory.language, sources=["github"], confidence=0.4)
    assert analyzer_api.github_strengths([topic, strong]) == [strong]  # repo topics are never skills


def test_new_cv_upload_forgets_old_reports(client):
    with_cv()
    assert client.post("/analyzer/run", data={"github_username": "demo"}).status_code == 200
    assert client.get("/analyzer/report").status_code == 200

    analyzer_api.clear_reports()
    assert client.get("/analyzer/report").status_code == 404

def test_run_with_a_portfolio_site(client, monkeypatch):
    with_cv()
    monkeypatch.setattr(analyzer_api.portfolio, "fetch_portfolio", lambda url: "Projects: a Python dashboard and an Excel model.")
    monkeypatch.setattr(
        analyzer_api.portfolio,
        "skills_from_portfolio",
        lambda text: ExtractedCV(skills=[Skill(name="Python", category=SkillCategory.tool, sources=["portfolio"]), Skill(name="Excel", category=SkillCategory.tool, sources=["portfolio"])]),
    )

    body = client.post("/analyzer/run", data={"portfolio_url": "https://example.test/me"}).json()

    assert body["sources"] == {"cv": 3, "portfolio": 2}
    assert {a["kind"] for a in body["anomalies"]} == {"overclaim"}  # Docker: Python and Excel are now backed
    assert body["integrity_score"] == 66.7
    assert next(c for c in body["clusters"] if c["name"] == "Excel")["sources"] == ["cv", "portfolio"]
    profile = session.get_profile()
    assert profile.evidence_sources == ["portfolio"]
    assert [(s.name, s.sources) for s in profile.skills] == [("Python", ["cv", "portfolio"]), ("Docker", ["cv"]), ("Excel", ["cv", "portfolio"])]


def test_unreadable_portfolio_is_a_422(client, monkeypatch):
    with_cv()

    def bad(url):
        raise analyzer_api.portfolio.PortfolioError("Could not fetch the portfolio: nope")

    monkeypatch.setattr(analyzer_api.portfolio, "fetch_portfolio", bad)
    response = client.post("/analyzer/run", data={"portfolio_url": "https://example.test"})
    assert response.status_code == 422 and "Could not fetch" in response.json()["detail"]

def test_run_with_portfolio_files(client, monkeypatch):
    with_cv()
    seen = []

    def fake_extract(text):
        seen.append(text)
        return ExtractedCV(skills=[Skill(name="Excel", category=SkillCategory.tool, sources=["portfolio"])])

    monkeypatch.setattr(analyzer_api.portfolio, "skills_from_portfolio", fake_extract)
    files = [
        ("portfolio_files", ("report.txt", b"Built an Excel forecasting model.", "text/plain")),
        ("portfolio_files", ("notes.txt", b"Dashboard write-up.", "text/plain")),
    ]

    body = client.post("/analyzer/run", files=files).json()

    assert body["sources"] == {"cv": 3, "portfolio": 1}
    assert "=== report.txt ===" in seen[0] and "=== notes.txt ===" in seen[0]  # both files, labelled
    assert next(c for c in body["clusters"] if c["name"] == "Excel")["sources"] == ["cv", "portfolio"]
    assert session.get_profile().evidence_sources == ["portfolio"]

    bad = [("portfolio_files", ("deck.pptx", b"xx", "application/octet-stream"))]
    assert client.post("/analyzer/run", files=bad).status_code == 422
