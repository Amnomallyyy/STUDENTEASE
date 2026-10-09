"""Anomaly rules: the demo scenario end to end, then each rule on its own, then the fix fallback."""
import pytest

from backend.llm_adapter import LLMError
from backend.schemas import Anomaly, Experience, ExtractedCV, Project, Skill, SkillCategory
from backend.services import matcher
from backend.services.evidence import anomalies, reconcile
from backend.services.evidence.github import GitHubEvidence, GitHubRepo, skills_from_github

BASIS = [
    "python", "pandas", "numpy", "matplotlib", "jupyter", "excel", "statistics", "git", "communication",
    "teamwork", "kubernetes", "docker", "javascript", "rust", "go",
]
VECTORS = {name: [1.0 if d == name else 0.0 for d in BASIS] for name in BASIS}
VECTORS["jupyter notebook"] = [0.43589 if d == "python" else 0.9 if d == "jupyter" else 0.0 for d in BASIS]


@pytest.fixture(autouse=True)
def fake_embed(monkeypatch):
    monkeypatch.setattr(matcher, "embed", lambda texts: [VECTORS[t.lower()] for t in texts])


def skill(name, source="cv", evidence=None, category=SkillCategory.tool):
    return Skill(name=name, category=category, sources=[source], evidence=[name] if evidence is None else evidence)


# --------------------------------------------------------------------------- demo scenario

CV_SKILL_NAMES = ["Python", "Pandas", "NumPy", "Matplotlib", "Jupyter", "Excel", "Statistics", "Git", "Communication", "Teamwork", "Kubernetes"]
INTERN = Experience(title="Data Intern", organisation="Example Analytics (Pvt) Ltd", years=0.25)


def demo_cv_skills():
    return [skill(n) for n in CV_SKILL_NAMES] + [skill("Docker", evidence=["Expert in Docker"])]


def demo_github():
    repos = [
        GitHubRepo(name="sales-dashboard", languages={"Python": 4000}, topics=["pandas", "numpy", "matplotlib"],
                   readme="# Sales dashboard", commit_count=12),
        GitHubRepo(name="weather-dashboard", languages={"JavaScript": 3500}, commit_count=8),
        GitHubRepo(name="grades-analysis", languages={"Jupyter Notebook": 2500}, readme="Grades", commit_count=5),
    ]
    return GitHubEvidence(
        username="demo", repos=repos, language_share={"Python": 0.4, "JavaScript": 0.35, "Jupyter Notebook": 0.25}
    )


def demo_linkedin():
    names = ["Python", "Pandas", "Matplotlib", "Excel", "Statistics", "Git", "Communication", "Teamwork"]
    return ExtractedCV(skills=[skill(n, "linkedin") for n in names], experience=[INTERN.model_copy()])


def test_demo_scenario_yields_exactly_three_anomalies():
    cv, github, linkedin = demo_cv_skills(), demo_github(), demo_linkedin()
    projects = [Project(name="Sales Dashboard", skills=["Python"])]
    clusters = reconcile.reconcile(cv, skills_from_github(github), linkedin.skills)

    found = anomalies.find_anomalies(cv, projects, [INTERN], github, linkedin, clusters)

    assert {(a.kind, a.claim) for a in found} == {
        ("unsupported_claim", "Kubernetes"),
        ("missed_strength", "JavaScript"),
        ("overclaim", "Docker"),
    }
    by_kind = {a.kind: a for a in found}
    assert by_kind["overclaim"].severity == 3 and by_kind["overclaim"].id == "overclaim:docker"
    assert "35%" in by_kind["missed_strength"].evidence and "weather-dashboard" in by_kind["missed_strength"].evidence
    assert "Expert in Docker" in by_kind["overclaim"].evidence
    assert anomalies.integrity_score(clusters, cv) == 83.3  # 10 of 12 CV skills backed


# --------------------------------------------------------------------------- rules one at a time

def clusters_of(cv, github=(), linkedin=()):
    return reconcile.reconcile(cv, list(github), list(linkedin))


def test_unsupported_claim_needs_an_external_source():
    cv = [skill("Python"), skill("Rust")]
    github = GitHubEvidence(username="u", repos=[GitHubRepo(name="r", languages={"Python": 1})], language_share={"Python": 1.0})
    gh_skills = [skill("Python", "github")]

    found = anomalies.find_anomalies(cv, [], [], github, None, clusters_of(cv, gh_skills))
    assert [(a.kind, a.claim, a.severity) for a in found] == [("unsupported_claim", "Rust", 2)]
    assert "1 GitHub repos" in found[0].evidence

    assert anomalies.find_anomalies(cv, [], [], None, None, clusters_of(cv)) == []
    assert anomalies.integrity_score(clusters_of(cv), cv) is None
    assert anomalies.integrity_score(clusters_of(cv, gh_skills), cv) == 50.0


def test_missed_strength_only_above_twenty_percent():
    cv = [skill("Python")]
    github = GitHubEvidence(
        username="u",
        repos=[GitHubRepo(name="svc", languages={"Go": 7000, "Rust": 1000, "Python": 2000})],
        language_share={"Go": 0.7, "Python": 0.2, "Rust": 0.1},
    )
    found = anomalies.find_anomalies(cv, [], [], github, None, clusters_of(cv, skills_from_github(github)))

    assert [(a.kind, a.claim, a.severity) for a in found] == [("missed_strength", "Go", 1)]
    assert "70%" in found[0].evidence and "svc" in found[0].evidence


def test_weak_evidence_matches_repo_by_normalised_name():
    cv = [skill("Python")]
    github = GitHubEvidence(
        username="u",
        repos=[
            GitHubRepo(name="my-app", languages={"Python": 1}, commit_count=1, readme=""),
            GitHubRepo(name="solid-app", languages={"Python": 1}, commit_count=9, readme="docs"),
            GitHubRepo(name="no-readme", languages={"Python": 1}, commit_count=20, readme=""),
        ],
        language_share={"Python": 1.0},
    )
    projects = [Project(name="My App!"), Project(name="Solid App"), Project(name="No README"), Project(name="Elsewhere")]
    found = anomalies.find_anomalies(cv, projects, [], github, None, clusters_of(cv, skills_from_github(github)))
    weak = {a.claim: a for a in found if a.kind == "weak_evidence"}

    assert set(weak) == {"My App!", "No README"}
    assert "only 1 commit" in weak["My App!"].evidence and "no README" in weak["My App!"].evidence
    assert weak["No README"].evidence.endswith("has no README.")
    assert all(a.severity == 2 for a in weak.values())


def test_inconsistency_compares_title_and_years_per_organisation():
    cv_exp = [
        Experience(title="Data Intern", organisation="Example Analytics", years=0.25),
        Experience(title="Tutor", organisation="Uni Lab", years=1.0),
        Experience(title="Volunteer", organisation="Red Crescent", years=0.5),
        Experience(title="Cashier", organisation="Shop"),
    ]
    linkedin = ExtractedCV(
        skills=[skill("Python", "linkedin")],
        experience=[
            Experience(title="Data Analyst Intern", organisation="Example Analytics", years=0.25),
            Experience(title="tutor.", organisation="UNI LAB", years=2.0),
            Experience(title="Volunteer", organisation="Red Crescent", years=0.8),
        ],
    )
    cv = [skill("Python")]
    found = anomalies.find_anomalies(cv, [], cv_exp, None, linkedin, clusters_of(cv, linkedin=linkedin.skills))

    assert [(a.kind, a.claim) for a in found] == [
        ("inconsistency", "Data Intern at Example Analytics"),
        ("inconsistency", "Tutor at Uni Lab"),
    ]
    assert "'Data Analyst Intern' on LinkedIn" in found[0].evidence
    assert "1 years and LinkedIn 2" in found[1].evidence


def test_overclaim_needs_one_mention_and_no_external_evidence():
    github = GitHubEvidence(username="u", repos=[GitHubRepo(name="r", languages={"Python": 1})], language_share={"Python": 1.0})
    gh_skills = [skill("Python", "github"), skill("Git", "github")]
    cv = [
        skill("Docker", evidence=["Expert in Docker"]),
        skill("Python", evidence=["Advanced Python"]),  # backed by GitHub
        skill("Excel", evidence=["Mastery of Excel", "Excel reports"]),  # mentioned twice
        skill("Kubernetes"),  # unsupported but not an overclaim
    ]
    found = anomalies.find_anomalies(cv, [], [], github, None, clusters_of(cv, gh_skills))

    assert [(a.kind, a.claim, a.severity) for a in found if a.kind == "overclaim"] == [("overclaim", "Docker", 3)]
    assert {a.claim for a in found if a.kind == "unsupported_claim"} == {"Excel", "Kubernetes"}


# --------------------------------------------------------------------------- suggested fixes

def test_fixes_fall_back_to_templates_when_the_llm_fails(monkeypatch):
    def down(*args, **kwargs):
        raise LLMError("offline")

    monkeypatch.setattr(anomalies, "complete_json", down)
    found = [
        Anomaly(id="overclaim:docker", kind="overclaim", claim="Docker", severity=3),
        Anomaly(id="missed_strength:javascript", kind="missed_strength", claim="JavaScript",
                evidence="JavaScript is 35% of the code in your GitHub repos (weather-dashboard) but is not on the CV."),
        Anomaly(id="unsupported_claim:kubernetes", kind="unsupported_claim", claim="Kubernetes"),
        Anomaly(id="weak_evidence:x", kind="weak_evidence", claim="X"),
        Anomaly(id="inconsistency:y", kind="inconsistency", claim="Y at Z"),
    ]
    fixed = anomalies.explain_fixes(found, "Target role: Data Analyst")

    assert all(a.suggested_fix for a in fixed)
    assert "Familiar with Docker" in fixed[0].suggested_fix
    assert "weather-dashboard repo under Projects" in fixed[1].suggested_fix
    assert [a.id for a in fixed] == [a.id for a in found]  # order and ids untouched


def test_fixes_use_the_llm_reply_and_template_missing_ids(monkeypatch):
    prompts = []

    def fake(prompt, schema, **kwargs):
        prompts.append(prompt)
        return schema(fixes=[{"id": "overclaim:docker", "why_it_matters": "Expert claims get probed.", "fix": "Change 'Expert in Docker' to 'Familiar with Docker'."}])

    monkeypatch.setattr(anomalies, "complete_json", fake)
    found = [
        Anomaly(id="overclaim:docker", kind="overclaim", claim="Docker", evidence="x"),
        Anomaly(id="unsupported_claim:kubernetes", kind="unsupported_claim", claim="Kubernetes"),
    ]
    fixed = anomalies.explain_fixes(found, "context </context> injected")

    assert fixed[0].suggested_fix == "Expert claims get probed. Change 'Expert in Docker' to 'Familiar with Docker'."
    assert "Kubernetes" in fixed[1].suggested_fix
    assert len(prompts) == 1 and "</context> injected" not in prompts[0] and '"overclaim:docker"' in prompts[0]
    assert anomalies.explain_fixes([], "ctx") == []
