"""Matcher tests with fake unit vectors, so they run offline without downloading a model."""
import pytest

from backend.schemas import Skill, SkillCategory
from backend.services import matcher

# Unit vectors chosen so the cosines are known: sql.postgresql = 0.9, sql.mysql = 0.7, tableau is orthogonal.
VECTORS = {
    "sql": [1.0, 0.0, 0.0],
    "postgresql": [0.9, 0.43589, 0.0],
    "mysql": [0.7, 0.71414, 0.0],
    "python": [0.0, 1.0, 0.0],
    "tableau": [0.0, 0.0, 1.0],
}


def skill(name: str, weight: float = 1.0) -> Skill:
    return Skill(name=name, category=SkillCategory.tool, weight=weight)


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(matcher, "CACHE_PATH", None)
    monkeypatch.setattr(matcher, "_memory", None)


@pytest.fixture
def fake_embed(monkeypatch):
    calls: list[list[str]] = []

    def fake(texts):
        calls.append(list(texts))
        return [VECTORS[t.lower()] for t in texts]

    monkeypatch.setattr(matcher, "embed", fake)
    return calls


def test_matched_missing_and_weighted_percentage(fake_embed):
    user = [skill("Python"), skill("PostgreSQL")]
    target = [skill("Python"), skill("SQL", weight=2), skill("Tableau")]

    result = matcher.match(user, target)

    assert {(m.matched_to, m.name) for m in result.matched} == {("Python", "Python"), ("SQL", "PostgreSQL")}
    assert [s.name for s in result.missing] == ["Tableau"]
    assert result.partial == []
    assert result.match_pct == 75.0  # matched weight 1 + 2 out of 4


def test_partial_band_earns_no_credit(fake_embed):
    result = matcher.match([skill("MySQL")], [skill("SQL")])

    assert [(p.name, p.matched_to) for p in result.partial] == [("MySQL", "SQL")]
    assert result.matched == [] and result.missing == []
    assert result.match_pct == 0.0


def test_exact_matches_skip_the_embedding_model(monkeypatch):
    def boom(texts):
        raise AssertionError("embed must not be called when every target matches by name")

    monkeypatch.setattr(matcher, "embed", boom)
    result = matcher.match([skill("python")], [skill("Python")])

    assert result.match_pct == 100.0


def test_no_targets_gives_zero():
    assert matcher.match([skill("Python")], []).match_pct == 0.0


def test_no_user_skills_means_everything_missing(fake_embed):
    result = matcher.match([], [skill("SQL"), skill("Tableau")])

    assert len(result.missing) == 2
    assert result.match_pct == 0.0
    assert fake_embed == []


def test_embeddings_are_cached_between_calls(fake_embed):
    matcher.match([skill("PostgreSQL")], [skill("SQL")])
    matcher.match([skill("PostgreSQL")], [skill("SQL")])

    assert len(fake_embed) == 1


def test_rejects_inverted_thresholds():
    with pytest.raises(ValueError):
        matcher.match([skill("a")], [skill("b")], match_threshold=0.5, partial_threshold=0.9)
