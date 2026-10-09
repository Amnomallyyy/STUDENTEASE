"""Request and response bodies for the REST API (see docs/api.md)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .job import JobMatch
from .profile import Location, MarketGap, MatchResult, UserMode


class GapResponse(BaseModel):
    role: str
    match: MatchResult
    market_gaps: list[MarketGap] = Field(default_factory=list)
    jobs_nearby: list[JobMatch] = Field(default_factory=list)


class AdjacentRole(BaseModel):
    role: str
    match_pct: float = Field(ge=0, le=100)


class ProfilePatch(BaseModel):
    """Fields the UI can change after the CV upload. Omitted or null means unchanged."""

    mode: UserMode | None = None
    target_role: str | None = None
    location: Location | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)
