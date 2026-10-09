"""Jobs API tests with a fake jobs.json (two listings near Karachi, one in Lahore) and the fake embedding."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import jobs as jobs_api  # noqa: E402
from backend.schemas import Job, Location, Profile, Skill, SkillCategory  # noqa: E402
from backend.services import session  # noqa: E402
from backend.services.data import DataMissing, JobNotFound  # noqa: E402

KARACHI = (24.8607, 67.0011)


def skill(name):
    return Skill(name=name, category=SkillCategory.tool)


JOBS = [
    Job(id="j1", company="Example Analytics", title="Junior Data Analyst", city="Karachi", lat=24.87, lng=67.02,
        required_skills=[skill("Python"), skill("Tableau")], source_url="https://example.org/jobs/1"),
    Job(id="j2", company="Port Data", title="SQL Analyst", city="Karachi", lat=24.90, lng=67.10,
        required_skills=[skill("SQL")], synthetic=True),
    Job(id="j3", company="Far Corp", title="Data Analyst", city="Hyderabad", lat=25.39, lng=68.37,  # ~150 km away
        required_skills=[skill("Python")]),
]


@pytest.fixture
def client(monkeypatch, fake_embed):
    session.reset_profile()
    monkeypatch.setattr(jobs_api, "load_jobs", lambda: list(JOBS))
    monkeypatch.setattr(jobs_api, "find_job", lambda job_id: next(j for j in JOBS if j.id == job_id))
    app = FastAPI()
    app.include_router(jobs_api.router)
    yield TestClient(app)
    session.reset_profile()


def with_cv(location=None):
    session.set_profile(Profile(skills=[skill("PostgreSQL"), skill("Python")], location=location))


def test_nearby_needs_a_cv_and_a_location(client):
    assert client.get("/jobs/nearby", params={"lat": 24.86, "lng": 67.0}).status_code == 409
    with_cv()
    assert client.get("/jobs/nearby").status_code == 422
    assert client.get("/jobs/nearby", params={"lat": 24.86, "lng": 67.0, "radius": 0}).status_code == 422


def test_nearby_scores_sorts_and_filters_by_radius(client):
    with_cv()

    body = client.get("/jobs/nearby", params={"lat": KARACHI[0], "lng": KARACHI[1]}).json()

    assert [j["id"] for j in body] == ["j2", "j1"]  # PostgreSQL ~ SQL = 100 %, Python-only = 50 %; Lahore is out
    sql_job, py_job = body
    assert sql_job["match_pct"] == 100.0 and sql_job["matched"] == ["SQL"] and sql_job["synthetic"] is True
    assert py_job["match_pct"] == 50.0 and py_job["missing"] == ["Tableau"]
    assert py_job["company"] == "Example Analytics" and py_job["lat"] == 24.87 and py_job["source_url"].endswith("/1")
    assert 0 < py_job["distance_km"] < sql_job["distance_km"] < 25


def test_nearby_falls_back_to_the_profile_location_and_honours_limit_and_min_match(client):
    with_cv(Location(lat=KARACHI[0], lng=KARACHI[1], city="Karachi"))

    assert [j["id"] for j in client.get("/jobs/nearby").json()] == ["j2", "j1"]
    assert [j["id"] for j in client.get("/jobs/nearby", params={"limit": 1}).json()] == ["j2"]
    assert [j["id"] for j in client.get("/jobs/nearby", params={"min_match": 60}).json()] == ["j2"]
    assert [j["id"] for j in client.get("/jobs/nearby", params={"radius": 500}).json()] == ["j2", "j3", "j1"]


def test_missing_dataset_is_a_503(client, monkeypatch):
    with_cv()

    def missing():
        raise DataMissing("jobs.json not found")

    monkeypatch.setattr(jobs_api, "load_jobs", missing)
    response = client.get("/jobs/nearby", params={"lat": 24.86, "lng": 67.0})
    assert response.status_code == 503 and "jobs.json" in response.json()["detail"]


def test_get_job_by_id(client, monkeypatch):
    assert client.get("/jobs/j1").json()["company"] == "Example Analytics"

    def unknown(job_id):
        raise JobNotFound(f"Unknown job id '{job_id}'")

    monkeypatch.setattr(jobs_api, "find_job", unknown)
    assert client.get("/jobs/zzz").status_code == 404
