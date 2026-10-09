"""The TypeScript types must match the Pydantic models. Regenerate with:
    python -m backend.schemas.generate_ts
"""
from backend.schemas import generate_ts


def test_generator_covers_the_shared_profile_contract():
    out = generate_ts.generate()

    assert "export interface Profile {" in out
    assert "  skills: Skill[];" in out
    assert "  gap: MatchResult | null;" in out
    assert 'export type UserMode = "student" | "job_seeker";' in out
    assert 'export type SkillCategory = "language"' in out


def test_profile_ts_is_up_to_date():
    assert generate_ts.main(["--check"]) == 0, "frontend/src/types/profile.ts is stale; run the generator"
