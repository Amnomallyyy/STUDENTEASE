"""Role-seeded interview questions that reference the user's own skills and projects. Owner: M3.

Falls back to a template bank (still seeded with the user's skills) when the LLM is unavailable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.llm_adapter import complete_json
from backend.schemas import Profile
from backend.schemas.interview import InterviewQuestion

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "question_gen.md"


class _Question(BaseModel):
    text: str = Field(description="The question, one sentence.")
    kind: Literal["behavioural", "technical", "situational"] = "behavioural"


class _Questions(BaseModel):
    questions: list[_Question] = Field(min_length=1, max_length=5)


def generate_questions(role: str, profile: Profile, count: int = 3) -> list[InterviewQuestion]:
    skills = top_skills(profile)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        mode="student" if profile.mode.value == "student" else "job seeker",
        role=role,
        count=count,
        skills=", ".join(skills) or "not provided",
        projects="; ".join(p.name for p in profile.projects[:4]) or "not provided",
        experience="; ".join(f"{e.title} at {e.organisation}" for e in profile.experience[:3]) or "not provided",
    )
    try:
        texts = [(q.text.strip(), q.kind) for q in complete_json(prompt, _Questions, temperature=0.7).questions]
    except Exception:  # LLMError, or a missing provider package / API key
        texts = []
    texts = [t for t in texts if t[0]][:count]
    if len(texts) < count:
        texts += [(t, "behavioural") for t in fallback_questions(role, skills, profile)][: count - len(texts)]
    return [InterviewQuestion(id=f"q{i + 1}", text=t, kind=k) for i, (t, k) in enumerate(texts)]


def top_skills(profile: Profile, n: int = 3) -> list[str]:
    """The user's strongest non-soft skills (by confidence and number of sources)."""
    ranked = sorted(
        (s for s in profile.skills if s.category != "soft_skill"),
        key=lambda s: (s.confidence, len(s.sources)),
        reverse=True,
    )
    return [s.name for s in ranked[:n]]


def fallback_questions(role: str, skills: list[str], profile: Profile) -> list[str]:
    skill = skills[0] if skills else "a tool you know well"
    other = skills[1] if len(skills) > 1 else "a new technology"
    project = profile.projects[0].name if profile.projects else None
    return [
        f"Tell me about a time you used {skill} to solve a real problem. What did you do, and what was the result?",
        (
            f"Walk me through your {project} project: what was hard, what did you personally do, and how did it turn out?"
            if project
            else "Describe a time you worked in a team and disagreed with someone. How did you handle it?"
        ),
        f"Tell me about a time you had to learn {other} quickly for a deadline. How did you approach it?",
        f"Why do you want to work as a {role}, and what have you done so far to prepare for it?",
    ]
