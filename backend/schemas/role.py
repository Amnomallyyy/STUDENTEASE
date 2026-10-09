"""Role and learning-resource contracts. Producer: M5 (data/roles.json, data/resources.json). Consumer: M1."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .skill import Skill


class Role(BaseModel):
    id: str
    name: str
    skills: list[Skill] = Field(default_factory=list, description="Weighted skills; weight reflects core vs preferred.")


class Resource(BaseModel):
    """One whitelisted free learning link. The roadmap may only cite URLs from this list."""

    title: str
    url: str
    hours: float = Field(default=4, ge=0)
