"""Reconciliation tests: alias grouping needs no model; near-synonym merging uses a fake embedding."""
import pytest

from backend.schemas import Skill, SkillCategory
from backend.services import matcher
from backend.services.evidence import reconcile

BASIS = ["javascript", "python", "jupyter", "excel"]
VECTORS = {name: [1.0 if d == name else 0.0 for d in BASIS] for name in BASIS}
VECTORS["jupyter notebook"] = [0.0, 0.43589, 0.9, 0.0]  # cosine 0.9 with "jupyter"


@pytest.fixture
def fake_embed(monkeypatch):
    calls = []

    def fake(texts):
        calls.append(list(texts))
        return [VECTORS[t.lower()] for t in texts]

    monkeypatch.setattr(matcher, "embed", fake)
    return calls


def skill(name, source="cv", evidence=()):
    return Skill(name=name, category=SkillCategory.tool, sources=[source], evidence=list(evidence))


def test_aliases_group_without_embedding(monkeypatch):
    def boom(texts):
        raise AssertionError("one cluster needs no embedding")

    monkeypatch.setattr(matcher, "embed", boom)
    clusters = reconcile.reconcile(
        [skill("JavaScript", evidence=["JavaScript", "JS and React"])], [skill("JS", "github")], [skill("js", "linkedin")]
    )

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.name == "JavaScript"  # CV spelling wins
    assert cluster.sources == ["cv", "github", "linkedin"]
    assert cluster.members == ["JavaScript", "JS", "js"]
    assert cluster.mention_count == 4  # 2 quotes + 1 minimum for each of the two quote-less members


def test_near_synonyms_merge_by_cosine_but_two_cv_skills_never_do(fake_embed):
    cv = [skill("Jupyter"), skill("Python"), skill("Excel")]
    github = [skill("Jupyter Notebook", "github"), skill("JavaScript", "github")]

    clusters = {c.name: c for c in reconcile.reconcile(cv, github, [])}

    assert set(clusters) == {"Jupyter", "Python", "Excel", "JavaScript"}
    assert clusters["Jupyter"].sources == ["cv", "github"]
    assert clusters["Jupyter"].members == ["Jupyter", "Jupyter Notebook"]
    assert reconcile.cluster_for(list(clusters.values()), "jupyter notebook") is clusters["Jupyter"]
    assert reconcile.cluster_for(list(clusters.values()), "Rust") is None
    assert len(fake_embed) == 1  # every cluster name embedded in one batch


def test_has_external():
    assert not reconcile.has_external(reconcile.reconcile([skill("Python")], [], [])[0])
    assert reconcile.has_external(reconcile.reconcile([], [skill("Python", "github")], [])[0])


def test_merge_evidence_tags_cv_skills_and_appends_external_only_ones(monkeypatch):
    monkeypatch.setattr(matcher, "embed", lambda texts: [VECTORS[t.lower()] for t in texts])
    cv = [skill("Python", evidence=["Python"]), skill("Excel")]
    github = [skill("JS", "github"), skill("python", "github")]
    linkedin = [skill("Excel", "linkedin"), skill("Jupyter Notebook", "linkedin")]
    clusters = reconcile.reconcile(cv, github, linkedin)

    merged = reconcile.merge_evidence(cv, github, linkedin, clusters)

    assert [(s.name, s.sources) for s in merged] == [
        ("Python", ["cv", "github"]),
        ("Excel", ["cv", "linkedin"]),
        ("JavaScript", ["github"]),
        ("Jupyter", ["linkedin"]),  # alias table canonicalises the name
    ]
    assert merged[0].evidence == ["Python"]  # CV objects keep their evidence quotes
