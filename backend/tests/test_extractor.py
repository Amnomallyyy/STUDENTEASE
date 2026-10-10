"""Extractor tests. The LLM call is replaced by a fake, so these run offline and need no API key."""
from backend.schemas import ExtractedCV, Skill, SkillCategory
from backend.services import extractor
from backend.services.normalize import canonical, normalize_skills

CV = """Jane Doe
Email: jane@example.com
Phone: +92 300 1234567
Date of Birth: 01/01/2000
Address: House 1, Street 2, Karachi

Data Intern, 2023 - 2024
Built a dashboard in Python and JS for weekly sales reports.
"""


def test_redact_pii_removes_contact_details_but_keeps_date_ranges():
    out = extractor.redact_pii(CV)
    assert "jane@example.com" not in out
    assert "1234567" not in out
    assert "01/01/2000" not in out
    assert "House 1" not in out
    assert "2023 - 2024" in out
    assert "Python" in out


def test_canonical_resolves_aliases():
    assert canonical("js") == "JavaScript"
    assert canonical("  Node  ") == "Node.js"
    assert canonical("Rust") == "Rust"  # unknown names pass through


def test_normalize_skills_merges_duplicates():
    skills = [
        Skill(name="JS", category=SkillCategory.language, evidence=["a"], sources=["cv"], years=1),
        Skill(name="JavaScript", category=SkillCategory.language, evidence=["b"], sources=["github"], years=3),
    ]
    merged = normalize_skills(skills)
    assert len(merged) == 1
    assert merged[0].name == "JavaScript"
    assert merged[0].evidence == ["a", "b"]
    assert merged[0].sources == ["cv", "github"]
    assert merged[0].years == 3


def test_extract_drops_skills_the_cv_does_not_support(monkeypatch):
    fake = ExtractedCV(
        skills=[
            Skill(name="Python", category=SkillCategory.language, evidence=["Built a dashboard in Python"]),
            Skill(name="JS", category=SkillCategory.language, evidence=["Python and JS"]),
            Skill(name="Kubernetes", category=SkillCategory.tool, evidence=["deployed on Kubernetes"]),
        ]
    )
    monkeypatch.setattr(extractor, "complete_json", lambda *args, **kwargs: fake)

    result = extractor.extract_from_text(CV)

    names = {s.name for s in result.skills}
    assert names == {"Python", "JavaScript"}
    assert all(s.sources == ["cv"] for s in result.skills)


def test_extract_empty_text_makes_no_llm_call(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("LLM must not be called for empty text")

    monkeypatch.setattr(extractor, "complete_json", boom)
    assert extractor.extract_from_text("   ").skills == []


def test_lexicon_pass_adds_skills_the_cv_names_but_the_model_skipped(monkeypatch):
    cv = """SKILLS
Programming: C++, Python
Core: DSA, OOP, Operating Systems
I like to go hiking.
"""
    monkeypatch.setattr(
        extractor, "complete_json", lambda *a, **k: ExtractedCV(skills=[Skill(name="Python", category=SkillCategory.language, evidence=["Programming: C++, Python"])])
    )

    result = extractor.extract_from_text(cv)

    names = [s.name for s in result.skills]
    assert names[0] == "Python"  # the model's answer comes first and keeps its confidence
    assert "Data Structures and Algorithms" in names and "Object-Oriented Programming" in names and "C++" in names
    assert "Go" not in names  # two-letter names are never matched in prose
    dsa = next(s for s in result.skills if s.name == "Data Structures and Algorithms")
    assert dsa.evidence == ["Core: DSA, OOP, Operating Systems"] and dsa.confidence == extractor.LEXICON_CONFIDENCE
    assert dsa.sources == ["cv"]
