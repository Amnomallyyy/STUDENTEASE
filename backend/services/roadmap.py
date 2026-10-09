"""4-week learning roadmap from the market-weighted gaps, using only whitelisted free resources.

If the LLM is unavailable or returns something unusable, a deterministic plan is built from the same
data, so the demo still shows a roadmap offline.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from backend.llm_adapter import LLMError, complete_json
from backend.schemas import Job, MarketGap, Resource, Roadmap, RoadmapTask, RoadmapWeek

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "roadmap.md"
MAX_SKILLS = 8
MAX_WEEKS = 4
DEFAULT_HOURS = 4.0
PIN_BOOST = 1.0


def build_roadmap(
    gaps: list[MarketGap],
    resources: dict[str, list[Resource]],
    *,
    role: str,
    pinned_job: Job | None = None,
    pinned_missing: Sequence[str] = (),
) -> Roadmap:
    """Plan up to 4 weeks. `pinned_missing` are the skills the user lacks for `pinned_job`; they move up."""
    pinned_id = pinned_job.id if pinned_job else None
    focus = reprioritise(gaps, pinned_missing)[:MAX_SKILLS]
    if not focus:
        return Roadmap(weeks=[], pinned_job_id=pinned_id)

    payload = {
        "role": role,
        "pinned_job": {"title": pinned_job.title, "company": pinned_job.company} if pinned_job else None,
        "skills": [
            {
                "skill": g.skill,
                "priority": g.priority,
                "jobs_requiring": g.jobs_requiring,
                "jobs_total": g.jobs_total,
                "resources": [r.model_dump() for r in resources.get(g.skill.lower(), [])[:3]],
            }
            for g in focus
        ],
    }
    prompt = f"{_instructions()}\n\n{json.dumps(payload, indent=2)}"
    try:
        cleaned = _clean(complete_json(prompt, Roadmap, max_tokens=2500), resources, pinned_id)
    except LLMError:
        cleaned = None
    return cleaned or fallback_roadmap(focus, resources, pinned_id)


def reprioritise(gaps: list[MarketGap], pinned_missing: Sequence[str] = ()) -> list[MarketGap]:
    """Boost the skills missing for a pinned job (adding any the market list lacks), highest priority first."""
    pinned = {name.lower() for name in pinned_missing}
    out: list[MarketGap] = []
    seen: set[str] = set()
    for gap in gaps:
        seen.add(gap.skill.lower())
        boost = PIN_BOOST if gap.skill.lower() in pinned else 0.0
        out.append(gap.model_copy(update={"priority": round(gap.priority + boost, 3)}))
    for name in pinned_missing:
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append(MarketGap(skill=name, jobs_requiring=0, jobs_total=0, priority=PIN_BOOST))
    return sorted(out, key=lambda g: (-g.priority, g.skill.lower()))


def fallback_roadmap(
    focus: list[MarketGap], resources: dict[str, list[Resource]], pinned_job_id: str | None = None
) -> Roadmap:
    """Deterministic plan: skills in priority order, split into consecutive weeks."""
    if not focus:
        return Roadmap(weeks=[], pinned_job_id=pinned_job_id)
    n_weeks = min(MAX_WEEKS, len(focus))
    per_week = math.ceil(len(focus) / n_weeks)
    weeks: list[RoadmapWeek] = []
    for i in range(n_weeks):
        chunk = focus[i * per_week : (i + 1) * per_week]
        if not chunk:
            break
        tasks = []
        for gap in chunk:
            options = resources.get(gap.skill.lower(), [])
            if options:
                tasks.append(RoadmapTask(title=options[0].title, skill=gap.skill, resource_url=options[0].url, hours=options[0].hours))
            else:
                tasks.append(RoadmapTask(title=f"Learn {gap.skill} fundamentals", skill=gap.skill, hours=DEFAULT_HOURS))
        weeks.append(RoadmapWeek(week=i + 1, focus=", ".join(g.skill for g in chunk), tasks=tasks))
    return Roadmap(weeks=weeks, pinned_job_id=pinned_job_id)


@lru_cache(maxsize=1)
def _instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _clean(draft: Roadmap, resources: dict[str, list[Resource]], pinned_job_id: str | None) -> Roadmap | None:
    """Enforce the whitelist and basic shape on the LLM's plan; None means unusable."""
    allowed = {r.url for items in resources.values() for r in items}
    weeks: list[RoadmapWeek] = []
    used: set[int] = set()
    for week in sorted(draft.weeks, key=lambda w: w.week):
        if week.week in used or not week.tasks:
            continue
        used.add(week.week)
        tasks = [
            task.model_copy(update={"resource_url": task.resource_url if task.resource_url in allowed else None, "done": False})
            for task in week.tasks
        ]
        weeks.append(week.model_copy(update={"tasks": tasks}))
    return Roadmap(weeks=weeks, pinned_job_id=pinned_job_id) if weeks else None
