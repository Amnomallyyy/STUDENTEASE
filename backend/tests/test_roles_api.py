"""GET /career/roles: the role picker's list (M2)."""
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import data


def test_roles_lists_every_role_with_skills():
    client = TestClient(app)
    response = client.get("/career/roles")
    assert response.status_code == 200
    roles = response.json()
    assert len(roles) == len(data.load_roles())
    first = roles[0]
    assert set(first) >= {"id", "name", "skills"}
    assert first["skills"] and {"name", "category", "weight"} <= set(first["skills"][0])


def test_roles_reports_missing_dataset(monkeypatch, tmp_path):
    monkeypatch.setenv("ROLES_PATH", str(tmp_path / "missing.json"))
    data.reload_data()
    try:
        response = TestClient(app).get("/career/roles")
        assert response.status_code == 503
        assert "roles" in response.json()["detail"].lower()
    finally:
        monkeypatch.delenv("ROLES_PATH")
        data.reload_data()
