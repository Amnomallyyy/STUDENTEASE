"""API tests with an in-process FastAPI app. Skipped when fastapi, httpx or python-multipart are missing."""
import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import career as career_api  # noqa: E402
from backend.api import chat as chat_api  # noqa: E402
from backend.api import profile as profile_api  # noqa: E402
from backend.schemas import ExtractedCV, Role, Skill, SkillCategory  # noqa: E402
from backend.services import career as career_service  # noqa: E402
from backend.services import session  # noqa: E402
from backend.services.data import DataMissing, RoleNotFound  # noqa: E402


def skill(name: str) -> Skill:
    return Skill(name=name, category=SkillCategory.tool)


@pytest.fixture
def client(monkeypatch):
    session.reset_profile()
    app = FastAPI()
    for module in (profile_api, career_api, chat_api):
        app.include_router(module.router)
    monkeypatch.setattr(profile_api, "extract_from_text", lambda text: ExtractedCV(skills=[skill("Python")]))
    yield TestClient(app)
    session.reset_profile()


def upload(client, name="cv.txt", content=b"I know Python well.", **data):
    return client.post("/profile/cv", files={"file": (name, content, "text/plain")}, data=data)


def test_new_session_starts_with_an_empty_profile(client):
    body = client.get("/profile").json()

    assert body["skills"] == [] and body["target_role"] is None


def test_cv_upload_stores_the_extracted_profile(client):
    response = upload(client, mode="job_seeker")

    assert response.status_code == 200
    assert response.json()["skills"][0]["name"] == "Python"
    stored = client.get("/profile").json()
    assert stored["mode"] == "job_seeker" and stored["skills"][0]["name"] == "Python"


def test_unsupported_and_empty_files_are_rejected(client):
    assert upload(client, name="cv.exe").status_code == 422
    assert upload(client, content=b"   ").status_code == 422


def test_a_cv_that_yields_no_skills_is_a_422_not_an_empty_profile(client, monkeypatch):
    monkeypatch.setattr(profile_api, "extract_from_text", lambda text: ExtractedCV())

    response = upload(client, content=b"P y t h o n  d e v e l o p e r")

    assert response.status_code == 422
    assert "No skills could be read" in response.json()["detail"]
    assert client.get("/profile").json()["skills"] == []  # nothing was stored


def test_patch_then_delete_my_data(client):
    upload(client)

    patched = client.patch(
        "/profile", json={"target_role": "Data Analyst", "location": {"lat": 24.86, "lng": 67.0, "city": "Karachi"}}
    ).json()
    assert patched["target_role"] == "Data Analyst" and patched["location"]["city"] == "Karachi"
    assert patched["skills"][0]["name"] == "Python"  # untouched fields stay

    assert client.delete("/profile").status_code == 204
    assert client.get("/profile").json()["skills"] == []


def test_gap_needs_a_cv_first(client):
    assert client.get("/career/gap", params={"role": "Data Analyst"}).status_code == 409


def test_gap_works_before_jobs_exist_and_is_saved_on_the_profile(client, monkeypatch, fake_embed):
    upload(client)
    monkeypatch.setattr(career_service, "find_role", lambda name: Role(id="da", name="Data Analyst", skills=[skill("Python"), skill("Tableau")]))

    def no_jobs():
        raise DataMissing("jobs.json not found")

    monkeypatch.setattr(career_service, "load_jobs", no_jobs)

    response = client.get("/career/gap", params={"role": "data analyst"})

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "Data Analyst"
    assert body["match"]["match_pct"] == 50.0
    assert [s["name"] for s in body["match"]["missing"]] == ["Tableau"]
    assert body["jobs_nearby"] == []
    assert client.get("/profile").json()["gap"]["match_pct"] == 50.0


def test_unknown_role_is_a_404(client, monkeypatch):
    upload(client)

    def unknown(name):
        raise RoleNotFound("Unknown role 'x'")

    monkeypatch.setattr(career_service, "find_role", unknown)

    assert client.get("/career/gap", params={"role": "x"}).status_code == 404


def test_chat_streams_server_sent_events(client, monkeypatch):
    events = [{"type": "text", "delta": "Hello"}, {"type": "done"}]
    monkeypatch.setattr(chat_api, "stream_reply", lambda message, history, profile: iter(events))

    response = client.post("/chat", json={"message": "hi"})

    assert response.headers["content-type"].startswith("text/event-stream")
    lines = [line for line in response.text.split("\n\n") if line]
    assert [json.loads(line.removeprefix("data: ")) for line in lines] == events


def test_chat_rejects_an_empty_message(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422
