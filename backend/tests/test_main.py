"""The assembled app (backend/main.py): health, built-with, CORS and router registration.

Skipped when fastapi or httpx are missing, like test_api.py. Data loaders are patched so the test does
not depend on data/*.json being present.
"""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.built_with import BUILT_WITH  # noqa: E402
from backend.services.data import DataMissing  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main.data, "load_roles", lambda: [1, 2, 3])
    monkeypatch.setattr(main.data, "load_jobs", lambda: [1] * 150)

    def no_resources():
        raise DataMissing("resources.json not found")

    monkeypatch.setattr(main.data, "load_resources", no_resources)
    return TestClient(main.app)


def test_health_reports_providers_and_data_counts(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Ollama")
    monkeypatch.setenv("EMBED_PROVIDER", "local")

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "ollama" and body["embed_provider"] == "local"
    assert body["data"] == {"roles": 3, "jobs": 150, "resources": None}


def test_built_with_lists_every_component(client):
    body = client.get("/built-with").json()

    assert len(body) == len(BUILT_WITH) > 0
    assert set(body[0]) == {"name", "kind", "licence", "url"}
    assert {i["kind"] for i in body} == {"model", "api", "dataset", "library"}


def test_acknowledgements_markdown_stays_in_sync_with_built_with():
    text = (ROOT / "ACKNOWLEDGEMENTS.md").read_text(encoding="utf-8")

    missing = [i["name"] for i in BUILT_WITH if i["name"] not in text]
    assert missing == [], f"regenerate: python -m backend.built_with > ACKNOWLEDGEMENTS.md (missing {missing})"


def test_cors_preflight_from_the_vite_dev_server(client):
    response = client.options(
        "/profile",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_origins_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://careerlens.vercel.app , http://localhost:5173,")

    assert main.cors_origins() == ["https://careerlens.vercel.app", "http://localhost:5173"]


@pytest.mark.parametrize("path", ["/profile", "/career/gap", "/chat", "/jobs/nearby", "/analyzer/run", "/health", "/built-with"])
def test_every_module_router_is_registered(path):
    # The OpenAPI schema lists every mounted route, whatever FastAPI's internal routing objects look like
    # (0.143 wraps included routers instead of flattening them into app.routes).
    assert path in main.app.openapi()["paths"]
