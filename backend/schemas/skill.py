"""Skill contract. Producer: M1. Consumers: M5 (jobs, anomalies), M3 (relevance)."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

SkillSource = Literal["cv", "github", "linkedin", "portfolio"]


class SkillCategory(str, Enum):
    language = "language"
    tool = "tool"
    framework = "framework"
    soft_skill = "soft_skill"
    domain = "domain"


class Skill(BaseModel):
    """One skill, as extracted from a CV / repo / LinkedIn export, or required by a role or job."""

    name: str = Field(description="Canonical name after alias normalisation, e.g. 'JavaScript' not 'JS'.")
    category: SkillCategory
    evidence: list[str] = Field(
        default_factory=list,
        description="Quoted spans from the source text that justify the skill. Empty = no direct evidence.",
    )
    sources: list[SkillSource] = Field(default_factory=list, description="Where the skill was seen.")
    years: float | None = Field(default=None, ge=0, description="Only if the source states it.")
    confidence: float = Field(default=1.0, ge=0, le=1)
    weight: float = Field(
        default=1.0,
        ge=0,
        description="Importance when this skill belongs to a role or job (core > preferred).",
    )
    requirement: Literal["core", "preferred"] | None = Field(
        default=None, description="Set on role/job skills only."
    )


class Project(BaseModel):
    name: str
    description: str = ""
    skills: list[str] = Field(default_factory=list, description="Canonical skill names used.")
    url: str | None = None


class Experience(BaseModel):
    title: str
    organisation: str = ""
    summary: str = ""
    years: float | None = Field(default=None, ge=0)
    skills: list[str] = Field(default_factory=list)


class ExtractedCV(BaseModel):
    """Structured output of the extractor LLM call (services/extractor.py)."""

    skills: list[Skill] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
