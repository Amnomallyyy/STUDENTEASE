"""Job listing contract. Producer: M5. Consumers: M1 (matching), M2 (map)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .skill import Skill


class Job(BaseModel):
    id: str
    company: str
    title: str
    city: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    requirements_text: str = ""
    required_skills: list[Skill] = Field(default_factory=list, description="Pre-extracted with M1's extractor.")
    source_url: str | None = None
    synthetic: bool = Field(default=False, description="True when the listing is generated, not public.")


class JobMatch(BaseModel):
    """A job scored against the user's skills (produced by api/jobs.py using M1's matcher)."""

    id: str
    match_pct: float = Field(ge=0, le=100)
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    distance_km: float = Field(ge=0)
