"""Interview routes end to end, offline: every LLM call fails, so the fallbacks must carry the flow."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.llm_adapter import LLMError
from backend.main import app
from backend.schemas import Profile, Skill
from backend.services import session
from backend.services.interview import nonverbal, questions, rewrite, scoring, star

FIXTURES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "vision" / "__fixtures__" / "answers.json"

ANSWER = (
    "So, um, last year during my internship at a logistics startup, the weekly sales report took two days to build by hand. "
    "My task was to automate it. I wrote a Python script with pandas that pulled the data from SQL and built the charts, "
    "and I set it up to run every Monday. As a result, the report took 10 minutes instead of two days."
)


@pytest.fixture
def client(monkeypatch):
    def no_llm(*_a, **_k):
        raise LLMError("offline")

    for module in (star, questions, rewrite, nonverbal):
        monkeypatch.setattr(module, "complete_json", no_llm)
    monkeypatch.setattr(scoring, "embed", no_llm)  # relevance falls back to word overlap
    session.set_profile(Profile(target_role="Data Analyst", skills=[Skill(name="Python", category="language")]))
    yield TestClient(app)
    session.reset_profile()


def test_full_interview_with_video(client):
    qs = client.post("/interview/start", json={}).json()
    assert [q["id"] for q in qs] == ["q1", "q2", "q3"]
    assert "Python" in qs[0]["text"]  # seeded with the user's own skill

    samples = json.loads(FIXTURES.read_text(encoding="utf-8"))["mixed"]["samples"]
    r = client.post("/interview/answer", data={"question_id": "q1", "transcript": ANSWER, "duration_s": "55", "samples": json.dumps(samples)})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["verbal"]["star"]["source"] == "rules"
    assert a["verbal"]["filler_counts"] == {"um": 1, "so": 1}
    # No embedding model in this test: relevance is left out rather than guessed.
    assert set(a["verbal"]["component_scores"]) == {"star", "conciseness", "fillers", "pace"}
    assert a["verbal"]["relevance"] is None
    assert a["non_verbal"]["body_language_score"] == 66.8
    assert 2 <= len(a["coaching_notes"]) <= 3
    assert a["rewritten_answer"].startswith("Last year")  # fillers and the leading "So," removed
    assert a["content_feedback"]

    report = client.get("/interview/report").json()
    assert report["readiness"] == pytest.approx(0.7 * report["verbal_score"] + 0.3 * 66.8, abs=0.1)
    assert report["fix_first"]
    assert session.get_profile().interview.readiness == report["readiness"]  # the chatbot can see it


def test_typed_answer_without_camera(client):
    client.post("/interview/start", json={"role": "Business Analyst"})
    a = client.post("/interview/answer", data={"question_id": "q2", "transcript": ANSWER}).json()
    assert a["non_verbal"] is None and a["coaching_notes"] == []
    assert a["verbal"]["pace_band"] == "unknown"
    assert "pace" not in a["verbal"]["component_scores"]
    report = client.get("/interview/report").json()
    assert report["non_verbal_score"] is None
    assert report["readiness"] == report["verbal_score"]


def test_errors(client):
    assert client.get("/interview/report").status_code in (200, 404)
    session.set_profile(Profile())
    assert client.post("/interview/start", json={}).status_code == 422  # no role anywhere
    client.post("/interview/start", json={"role": "Data Analyst"})
    assert client.post("/interview/answer", data={"question_id": "q9", "transcript": "hi"}).status_code == 404
    assert client.post("/interview/answer", data={"question_id": "q1", "transcript": "  "}).status_code == 422
    assert client.post("/interview/answer", data={"question_id": "q1", "transcript": "x", "samples": "not json"}).status_code == 422


def test_verbal_score_reweights_without_pace():
    full = {"star": 100, "conciseness": 100, "fillers": 100, "relevance": 100, "pace": 0}
    assert scoring.verbal_score(full) == 90.0
    del full["pace"]
    assert scoring.verbal_score(full) == 100.0


def test_content_feedback_names_the_missing_result():
    s = star.rule_based_star("Last year at my internship we had a slow report. I wrote a script to fix it.")
    v = scoring.verbal_metrics("Tell me about a time you automated something.", "Last year at my internship we had a slow report. I wrote a script to fix it.", 0, s)
    assert "Result" in scoring.content_feedback(v)[0]


def test_relevance_is_scored_when_embeddings_work(monkeypatch):
    monkeypatch.setattr(scoring, "embed", lambda texts: [[1.0, 0.0], [0.6, 0.8]])  # cosine 0.6
    s = star.rule_based_star(ANSWER)
    v = scoring.verbal_metrics("Q?", ANSWER, 0, s)
    assert v.relevance == 0.6
    assert v.component_scores["relevance"] == 100.0


def test_rewrite_fallback_removes_fillers():
    assert rewrite.strip_fillers("So, um, it was, like, slow and like, I fixed it.") == "it was, slow and I fixed it."
