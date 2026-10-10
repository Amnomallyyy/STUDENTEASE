"""The shared Profile object: the single source of truth every module reads from and writes to.

Producer: M1 -> everyone. frontend/src/types/profile.ts is generated from this file.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .interview import InterviewReport
from .job import JobMatch
from .skill import Experience, Project, Skill, SkillSource


class UserMode(str, Enum):
    student = "student"
    job_seeker = "job_seeker"


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    city: str = ""


class SkillMatch(BaseModel):
    name: str
    matched_to: str = Field(description="The target skill this user skill was matched against.")
    similarity: float = Field(ge=0, le=1)
    sources: list[SkillSource] = Field(
        default_factory=list, description="Where the user skill was seen (cv, github, linkedin); set by the Analyzer."
    )


class MatchResult(BaseModel):
    """Output of services/matcher.py. Cosine >= 0.80 is matched, 0.65-0.80 is partial."""

    match_pct: float = Field(ge=0, le=100, description="Weighted matched / weighted total.")
    evidenced_pct: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Like match_pct but counting only skills backed by GitHub or LinkedIn. None until the Analyzer has run.",
    )
    matched: list[SkillMatch] = Field(default_factory=list)
    partial: list[SkillMatch] = Field(default_factory=list)
    missing: list[Skill] = Field(default_factory=list)


class MarketGap(BaseModel):
    """One missing skill, ranked by how many nearby jobs ask for it (services/differential.py)."""

    skill: str
    jobs_requiring: int = Field(ge=0)
    jobs_total: int = Field(ge=0)
    priority: float = Field(ge=0, description="Role weight combined with market demand.")


class Anomaly(BaseModel):
    """A CV claim the evidence does not support. Producer: M5 (anomalies.py)."""

    id: str
    kind: str = Field(description="Rule name, e.g. invented_skill, missing_repo, overclaim.")
    claim: str
    evidence: str = ""
    severity: int = Field(default=1, ge=1, le=3)
    suggested_fix: str = ""


class RoadmapTask(BaseModel):
    title: str
    skill: str
    resource_url: str | None = Field(default=None, description="Must come from data/resources.json.")
    hours: float = Field(default=1, ge=0)
    done: bool = False


class RoadmapWeek(BaseModel):
    week: int = Field(ge=1, le=4)
    focus: str
    tasks: list[RoadmapTask] = Field(default_factory=list)


class Roadmap(BaseModel):
    weeks: list[RoadmapWeek] = Field(default_factory=list)
    pinned_job_id: str | None = None


class Profile(BaseModel):
    mode: UserMode = UserMode.student
    target_role: str | None = None
    location: Location | None = None

    skills: list[Skill] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)

    gap: MatchResult | None = None
    market_gaps: list[MarketGap] = Field(default_factory=list)
    jobs_nearby: list[JobMatch] = Field(default_factory=list)
    roadmap: Roadmap | None = None

    anomalies: list[Anomaly] = Field(default_factory=list)
    integrity_score: float | None = Field(default=None, ge=0, le=100)
    evidence_sources: list[SkillSource] = Field(
        default_factory=list,
        description="External sources the Analyzer has checked (github, linkedin). Empty until POST /analyzer/run.",
    )

    interview: InterviewReport | None = None
