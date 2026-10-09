"""Analyzer and jobs-map contracts. Producer: M5 (api/analyzer.py, api/jobs.py). Consumer: M2 (UI, map).

Import from `backend.schemas.analyzer` directly; these models are not re-exported by the package.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .job import JobMatch
from .profile import Anomaly
from .skill import SkillSource


class SkillCluster(BaseModel):
    """One skill seen across sources, after alias and embedding merging (services/evidence/reconcile.py)."""

    name: str = Field(description="Canonical name; the CV spelling wins when the sources disagree.")
    sources: list[SkillSource] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list, description="Every distinct name merged into this cluster.")
    mention_count: int = Field(default=1, ge=1, description="Evidence quotes across members, at least 1 per member.")


class AnalyzerReport(BaseModel):
    report_id: str
    anomalies: list[Anomaly] = Field(default_factory=list)
    integrity_score: float | None = Field(default=None, ge=0, le=100)
    clusters: list[SkillCluster] = Field(default_factory=list)
    sources: dict[str, int] = Field(default_factory=dict, description="Skill count per source, e.g. {'cv': 12}.")
    github_username: str | None = None


class JobNearby(JobMatch):
    """A scored job plus the listing fields the map needs for its pins (superset of JobMatch)."""

    company: str
    title: str
    city: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    synthetic: bool = False
    source_url: str | None = None
