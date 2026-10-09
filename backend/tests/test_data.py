import json

import pytest

from backend.services import data


@pytest.fixture(autouse=True)
def fresh_data():
    data.reload_data()
    yield
    data.reload_data()


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


ROLE = {"id": "data-analyst", "name": "Data Analyst", "skills": [{"name": "SQL", "category": "language", "weight": 3}]}


def test_find_role_by_id_or_name_ignoring_case(monkeypatch, tmp_path):
    monkeypatch.setenv("ROLES_PATH", str(write(tmp_path, "roles.json", [ROLE])))

    assert data.find_role("DATA ANALYST").id == "data-analyst"
    assert data.find_role("data-analyst").name == "Data Analyst"


def test_unknown_role_lists_the_available_ones(monkeypatch, tmp_path):
    monkeypatch.setenv("ROLES_PATH", str(write(tmp_path, "roles.json", [ROLE])))

    with pytest.raises(data.RoleNotFound, match="Data Analyst"):
        data.find_role("Astronaut")


def test_missing_file_raises_data_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBS_PATH", str(tmp_path / "nope.json"))

    with pytest.raises(data.DataMissing):
        data.load_jobs()


def test_malformed_file_raises_data_error_not_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("ROLES_PATH", str(write(tmp_path, "roles.json", [{"id": "x"}])))

    with pytest.raises(data.DataError) as info:
        data.load_roles()

    assert not isinstance(info.value, data.DataMissing)


def test_invalid_json_raises_data_error(monkeypatch, tmp_path):
    monkeypatch.setenv("ROLES_PATH", str(write(tmp_path, "roles.json", "{not json")))

    with pytest.raises(data.DataError, match="not valid JSON"):
        data.load_roles()


def test_resources_are_keyed_by_lowercase_skill(monkeypatch, tmp_path):
    raw = {"SQL": [{"title": "SQL Basics", "url": "https://example.org/sql", "hours": 6}]}
    monkeypatch.setenv("RESOURCES_PATH", str(write(tmp_path, "resources.json", raw)))

    assert data.load_resources()["sql"][0].title == "SQL Basics"


def test_find_job(monkeypatch, tmp_path):
    job = {"id": "j1", "company": "Acme", "title": "Analyst", "city": "Karachi", "lat": 24.86, "lng": 67.0}
    monkeypatch.setenv("JOBS_PATH", str(write(tmp_path, "jobs.json", [job])))

    assert data.find_job("j1").company == "Acme"
    with pytest.raises(data.JobNotFound):
        data.find_job("zzz")
