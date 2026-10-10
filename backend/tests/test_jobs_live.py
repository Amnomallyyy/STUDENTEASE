"""Live job source: JSearch v2 reply parsing, with the network faked."""
import pytest

from backend.schemas import Location
from backend.services import jobs_live

ROW = {
    "job_id": "abc123",
    "job_title": "Data Analyst (Contract)",
    "employer_name": "PrimeDefense USA",
    "job_publisher": "LinkedIn",
    "job_city": "Karachi",
    "job_country": "PK",
    "job_latitude": 24.86,
    "job_longitude": 67.0,
    "job_apply_link": "https://www.linkedin.com/jobs/view/1",
    "job_posted_at": "5 days ago",
    "job_description": "We need SQL, Excel and Power BI. Python is a plus.",
    "job_highlights": ["Qualifications: Tableau"],
}


@pytest.fixture
def live(monkeypatch, tmp_path):
    monkeypatch.setenv("RAPIDAPI_KEY", "k")
    monkeypatch.setenv("JOBS_SOURCE", "live")
    monkeypatch.setattr(jobs_live, "CACHE_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(jobs_live, "_country", lambda location: "pk")


def test_v2_reply_becomes_jobs_with_skills_and_attribution(live, monkeypatch):
    calls = []

    class R:
        status_code = 200
        ok = True

        def json(self):
            return {"status": "OK", "data": {"jobs": [ROW, {"job_title": "", "employer_name": "x"}], "cursor": None}}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        return R()

    monkeypatch.setattr(jobs_live.requests, "get", fake_get)

    jobs = jobs_live.jobs_for("Data Analyst", Location(lat=24.86, lng=67.0, city="Karachi"))

    assert calls[0][0].endswith("/search-v2") and calls[0][1]["country"] == "pk"
    assert len(jobs) == 1  # the row without a title is dropped
    job = jobs[0]
    assert job.id == "js-abc123" and job.source_name == "LinkedIn" and job.posted_at == "5 days ago"
    assert job.synthetic is False and job.source_url.startswith("https://www.linkedin.com")
    assert {s.name for s in job.required_skills} >= {"SQL", "Excel", "Power BI", "Python", "Tableau"}

    jobs_live.jobs_for("Data Analyst", Location(lat=24.86, lng=67.0, city="Karachi"))
    assert len(calls) == 1  # second call served from the disk cache


def test_quota_and_key_errors_are_user_safe(live, monkeypatch):
    class R:
        def __init__(self, code):
            self.status_code = code
            self.ok = code < 400

        def json(self):
            return {}

    monkeypatch.setattr(jobs_live.requests, "get", lambda *a, **k: R(429))
    with pytest.raises(jobs_live.JobsUnavailable, match="quota"):
        jobs_live.search_jobs("x", "y")
    monkeypatch.setattr(jobs_live.requests, "get", lambda *a, **k: R(403))
    with pytest.raises(jobs_live.JobsUnavailable, match="API key"):
        jobs_live.search_jobs("x2", "y")


def test_without_a_key_the_sample_dataset_is_used(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    monkeypatch.delenv("JOBS_SOURCE", raising=False)
    assert jobs_live.source() == "dataset"

def test_thin_postings_are_topped_up_with_the_role_core_skills(live, monkeypatch):
    from backend.schemas import Role, Skill, SkillCategory

    core = [Skill(name=n, category=SkillCategory.tool, requirement="core", weight=3) for n in ("SQL", "Excel", "Python")]
    monkeypatch.setattr(jobs_live, "find_role", lambda name: Role(id="da", name="Data Analyst", skills=core))

    thin = jobs_live._required_skills("We need an Excel wizard.", jobs_live._role_core("Data Analyst"))
    assert [(s.name, s.requirement) for s in thin] == [("Excel", "core"), ("SQL", "preferred"), ("Python", "preferred")]

    rich = jobs_live._required_skills("SQL, Excel, Python and Tableau required.", jobs_live._role_core("Data Analyst"))
    assert all(s.requirement == "core" for s in rich) and len(rich) >= 3  # nothing implied when the advert is specific
