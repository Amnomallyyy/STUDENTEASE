"""Checks on the committed datasets in data/ (built by scripts/build_roles.py and scripts/build_jobs.py).

These load the real files, so they also guard the demo numbers: the demo CV must land at 50-70 % for
Data Analyst, and Karachi must have enough nearby jobs for the market view.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from backend.schemas import Skill, SkillCategory
from backend.services import data, matcher, normalize
from backend.services.geo import haversine_km, nearby_jobs

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_jobs  # noqa: E402
import build_roles  # noqa: E402

CITY_CENTRES = {"Karachi": (24.8607, 67.0011), "Lahore": (31.5204, 74.3587), "Islamabad": (33.6844, 73.0479)}
KARACHI = CITY_CENTRES["Karachi"]

DEMO_CV = ["Python", "Pandas", "NumPy", "Matplotlib", "Jupyter", "Excel", "Statistics", "Git",
           "Communication", "Teamwork", "Kubernetes", "Docker"]


@pytest.fixture(autouse=True)
def fresh_data():
    data.reload_data()
    yield
    data.reload_data()


@pytest.fixture
def zero_embed(monkeypatch):
    """Embedding stub: every vector is zero, so only exact names can match. Records the calls."""
    calls: list[list[str]] = []

    def fake(texts):
        calls.append(list(texts))
        return [[0.0] * 8 for _ in texts]

    monkeypatch.setattr(matcher, "embed", fake)
    return calls


def skill_names(role) -> set[str]:
    return {s.name for s in role.skills}


# --------------------------------------------------------------------------- roles

def test_roles_load_with_expected_shape():
    roles = data.load_roles()

    assert 20 <= len(roles) <= 30
    assert len({r.id for r in roles}) == len(roles)
    for role in roles:
        assert 10 <= len(role.skills) <= 20, role.name
        assert len(skill_names(role)) == len(role.skills), f"{role.name} repeats a skill"
        for s in role.skills:
            assert s.requirement in ("core", "preferred")
            assert s.weight == (3 if s.requirement == "core" else 1)


def test_one_canonical_spelling_per_skill():
    names = {s.name for role in data.load_roles() for s in role.skills}
    assert len({n.lower() for n in names}) == len(names)


def test_find_role_data_analyst():
    role = data.find_role("Data Analyst")

    assert role.id == "data-analyst"
    core = {s.name for s in role.skills if s.requirement == "core"}
    assert {"SQL", "Excel", "Python", "Statistics", "Data Visualization"} <= core
    assert {"Tableau", "Power BI", "Pandas", "Communication"} <= skill_names(role)


def test_demo_cv_matches_data_analyst_between_50_and_70(zero_embed):
    user = [Skill(name=n, category=SkillCategory.tool) for n in DEMO_CV]
    result = matcher.match(user, data.find_role("Data Analyst").skills)

    assert 50 <= result.match_pct <= 70
    assert {m.matched_to for m in result.matched} >= {"Python", "Excel", "Statistics", "Pandas"}
    assert "SQL" in {s.name for s in result.missing}
    assert result.match_pct == build_roles.demo_match_pct(build_roles.build_roles())


# --------------------------------------------------------------------------- resources and aliases

def test_every_role_skill_has_a_resource():
    resources = data.load_resources()
    missing = {s.name for role in data.load_roles() for s in role.skills if not resources.get(s.name.lower())}
    assert not missing
    for items in resources.values():
        assert 1 <= len(items) <= 3
        for r in items:
            assert r.url.startswith("https://")
            assert r.hours > 0


def test_aliases_file_maps_variants_to_canonical_names(monkeypatch):
    raw = json.loads((DATA_DIR / "skill_aliases.json").read_text(encoding="utf-8"))
    role_skills = {s.name for role in data.load_roles() for s in role.skills}
    assert all(isinstance(v, list) and v for v in raw.values())
    assert set(raw) <= role_skills

    monkeypatch.delenv("SKILL_ALIASES_PATH", raising=False)
    normalize.reload_aliases()
    try:
        assert normalize.canonical("Jupyter Notebook") == "Jupyter"
        assert normalize.canonical("PowerBI") == "Power BI"
        assert normalize.canonical("Postgres") == "PostgreSQL"
        assert normalize.canonical("Golang") == "Go"
    finally:
        normalize.reload_aliases()


# --------------------------------------------------------------------------- jobs

def test_jobs_load_with_expected_shape():
    jobs = data.load_jobs()

    assert 150 <= len(jobs) <= 300
    assert len({j.id for j in jobs}) == len(jobs)
    for job in jobs:
        assert job.synthetic is True
        assert job.source_url is None
        assert job.city in CITY_CENTRES
        assert 5 <= len(job.required_skills) <= 10
        assert job.requirements_text.count(". ") >= 1  # at least two sentences


def test_job_skills_use_canonical_role_skill_names():
    role_skills = {s.name for role in data.load_roles() for s in role.skills}
    for job in data.load_jobs():
        for s in job.required_skills:
            assert s.name in role_skills, f"{job.id}: {s.name}"
            assert s.name.lower() in job.requirements_text.lower(), f"{job.id} text does not mention {s.name}"


def test_jobs_are_near_their_city_centre():
    for job in data.load_jobs():
        lat, lng = CITY_CENTRES[job.city]
        assert haversine_km(lat, lng, job.lat, job.lng) <= 30, job.id


def test_each_city_has_data_analyst_listings():
    jobs = data.load_jobs()
    for city in CITY_CENTRES:
        assert sum("Data Analyst" in j.title for j in jobs if j.city == city) >= 15, city


def test_karachi_has_a_market_sample_within_25km():
    pairs = nearby_jobs(data.load_jobs(), KARACHI, 25)

    assert len(pairs) >= 20
    assert all(distance <= 25 for _, distance in pairs)


def test_most_karachi_analyst_jobs_ask_for_sql():
    analysts = [
        j for j in data.load_jobs()
        if j.city == "Karachi" and any(r in j.title for r in build_jobs.ANALYST_ROLES)
    ]
    with_sql = [j for j in analysts if any(s.name == "SQL" for s in j.required_skills)]

    assert 0.6 <= len(with_sql) / len(analysts) <= 0.8


# --------------------------------------------------------------------------- build scripts

def test_build_roles_is_idempotent():
    assert build_roles.build_roles() == json.loads((DATA_DIR / "roles.json").read_text(encoding="utf-8"))
    assert build_roles.build_aliases() == json.loads((DATA_DIR / "skill_aliases.json").read_text(encoding="utf-8"))
    assert build_roles.build_resources() == json.loads((DATA_DIR / "resources.json").read_text(encoding="utf-8"))
    assert not build_roles.check(build_roles.build_roles(), build_roles.build_aliases(), build_roles.build_resources())


def test_build_jobs_is_idempotent():
    assert build_jobs.build_jobs() == json.loads((DATA_DIR / "jobs.json").read_text(encoding="utf-8"))
    assert not build_jobs.problems(build_jobs.build_jobs())
