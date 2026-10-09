"""Shared fixtures: an isolated embedding cache and a fake embedding model with known similarities."""
import pytest

from backend.services import matcher

DIMS = ["sql", "python", "tableau", "excel", "docker", "statistics", "git", "communication"]


def _vec(**weights: float) -> list[float]:
    return [weights.get(d, 0.0) for d in DIMS]


# One orthogonal unit vector per skill, plus two near-neighbours of SQL with known cosines:
# sql . postgresql = 0.9 (matched), sql . mysql = 0.7 (partial).
VECTORS = {d: _vec(**{d: 1.0}) for d in DIMS}
VECTORS["postgresql"] = _vec(sql=0.9, python=0.43589)
VECTORS["mysql"] = _vec(sql=0.7, python=0.71414)


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(matcher, "CACHE_PATH", None)
    monkeypatch.setattr(matcher, "_memory", None)


@pytest.fixture
def fake_embed(monkeypatch):
    """Replace the embedding model. Returns the list of calls so tests can assert on model usage."""
    calls: list[list[str]] = []

    def fake(texts):
        calls.append(list(texts))
        return [VECTORS[t.lower()] for t in texts]

    monkeypatch.setattr(matcher, "embed", fake)
    return calls
