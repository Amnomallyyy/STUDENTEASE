"""Profile-grounded career chatbot with three tool calls.

Every message is sent with a compact summary of the user's Profile in the system prompt (no vector
database needed at this size). The model can call get_jobs_near_me, explain_gap and
start_mock_interview; each call returns data for the model and a UI action for the front end.

stream_reply() yields events the API sends as server-sent events. The front end switches on "type":
    {"type": "open_map", "radius_km": 25.0, "keyword": "data" | null}   show the job map with this filter
    {"type": "open_career_map", "role": "Data Analyst"}                  show the career map for a role
    {"type": "open_interview", "role": "Data Analyst"}                   start the mock interview
    {"type": "text", "delta": "..."}                                     a piece of the answer
    {"type": "done"}
    {"type": "error", "message": "..."}
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from backend.llm_adapter import LLMError, chat
from backend.schemas import ChatMessage, Profile, UserMode
from backend.services import career, differential, jobs_live
from backend.services.data import DataError, JobNotFound, RoleNotFound, find_role
from backend.services.geo import nearby_jobs

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "chat_system.md"
MAX_TOOL_ROUNDS = 3
HISTORY_TURNS = 10
CHUNK_CHARS = 40

MODE_GUIDANCE = {
    UserMode.student: "The user is a student. Favour internships, projects, portfolio building and what to learn next.",
    UserMode.job_seeker: (
        "The user is a job seeker. Favour which jobs to apply to first, application and interview preparation. "
        "Give no salary figures; you have no salary data."
    ),
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_jobs_near_me",
        "description": "List the jobs closest to the user that best match their skills, optionally filtered by a keyword.",
        "parameters": {
            "type": "object",
            "properties": {
                "radius_km": {"type": "number", "description": "Search radius in kilometres (default 25)."},
                "keyword": {"type": "string", "description": "Optional word to look for in title, company or requirements."},
            },
            "required": ["radius_km"],
        },
    },
    {
        "name": "explain_gap",
        "description": "Explain how close the user is to a role: matched, partial and missing skills, and what the market asks for most.",
        "parameters": {
            "type": "object",
            "properties": {"role": {"type": "string", "description": "Role name, e.g. 'Data Analyst'."}},
            "required": ["role"],
        },
    },
    {
        "name": "start_mock_interview",
        "description": "Start a mock interview for a role.",
        "parameters": {
            "type": "object",
            "properties": {"role": {"type": "string", "description": "Role name to interview for."}},
            "required": ["role"],
        },
    },
]


# --------------------------------------------------------------------------- context

def build_context(profile: Profile) -> dict[str, Any]:
    """A compact, personal-detail-free summary of the profile for the system prompt."""
    ctx: dict[str, Any] = {
        "mode": profile.mode.value,
        "target_role": profile.target_role,
        "city": profile.location.city if profile.location and profile.location.city else None,
        "skills": [{"name": s.name, "sources": s.sources, "years": s.years} for s in profile.skills[:40]],
    }
    if profile.gap:
        ctx["role_match"] = {
            "match_pct": profile.gap.match_pct,
            "matched": [m.matched_to for m in profile.gap.matched],
            "partial": [m.matched_to for m in profile.gap.partial],
            "missing": [s.name for s in profile.gap.missing],
        }
    ctx["market_gaps"] = [
        {"skill": g.skill, "jobs_requiring": g.jobs_requiring, "jobs_total": g.jobs_total} for g in profile.market_gaps[:5]
    ]
    ctx["anomalies"] = [
        {"kind": a.kind, "claim": a.claim, "suggested_fix": a.suggested_fix} for a in profile.anomalies[:8]
    ]
    ctx["integrity_score"] = profile.integrity_score
    if profile.interview:
        iv = profile.interview
        ctx["interview"] = {
            "role": iv.role,
            "readiness": iv.readiness,
            "verbal_score": iv.verbal_score,
            "non_verbal_score": iv.non_verbal_score,
            "fix_first": iv.fix_first,
            "answers": [
                {
                    "question": a.question.text,
                    "verbal_score": a.verbal_score,
                    "star_missing": [
                        part for part in ("situation", "task", "action", "result") if not getattr(a.verbal.star, part).present
                    ],
                    "fillers_per_100_words": a.verbal.fillers_per_100_words,
                    "wpm": a.verbal.wpm,
                }
                for a in iv.answers
            ],
        }
    if profile.roadmap and profile.roadmap.weeks:
        ctx["roadmap"] = [{"week": w.week, "focus": w.focus} for w in profile.roadmap.weeks]
    ctx["top_jobs_nearby"] = [
        {"id": j.id, "match_pct": j.match_pct, "missing": j.missing, "distance_km": j.distance_km}
        for j in profile.jobs_nearby[:5]
    ]
    return {k: v for k, v in ctx.items() if v not in (None, [], {})}


@lru_cache(maxsize=1)
def _instructions() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def system_prompt(profile: Profile) -> str:
    return (
        f"{_instructions()}\n\n## Mode\n{MODE_GUIDANCE[profile.mode]}\n\n"
        f"## User profile (JSON)\n{json.dumps(build_context(profile), indent=2)}"
    )


# --------------------------------------------------------------------------- tools

def run_tool(name: str, args: dict[str, Any], profile: Profile) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Execute one tool call. Returns (result for the model, UI action or None)."""
    try:
        if name == "get_jobs_near_me":
            return _tool_jobs(args, profile)
        if name == "explain_gap":
            return _tool_gap(args, profile)
        if name == "start_mock_interview":
            return _tool_interview(args)
        return {"error": f"Unknown tool '{name}'."}, None
    except (RoleNotFound, JobNotFound, DataError) as exc:
        return {"error": str(exc)}, None


def _number(value: Any, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def _tool_jobs(args: dict[str, Any], profile: Profile) -> tuple[dict[str, Any], dict[str, Any]]:
    radius = _number(args.get("radius_km"), career.DEFAULT_RADIUS_KM, 1, 200)
    keyword = str(args.get("keyword") or "").strip().lower()
    location = (profile.location.lat, profile.location.lng) if profile.location else None
    try:
        jobs = jobs_live.jobs_for(profile.target_role, profile.location)
    except (DataError, jobs_live.JobsUnavailable) as exc:
        return {"location_known": location is not None, "jobs_found": 0, "error": str(exc)}, {}
    pairs = nearby_jobs(jobs, location, radius)
    if keyword:
        pairs = [(j, d) for j, d in pairs if keyword in f"{j.title} {j.company} {j.requirements_text}".lower()]
    scored = sorted(
        ((differential.score_job(profile.skills, job, dist), job) for job, dist in pairs),
        key=lambda pair: -pair[0].match_pct,
    )[:5]
    result = {
        "location_known": location is not None,
        "jobs_found": len(pairs),
        "radius_km": radius,
        "top_matches": [
            {
                "company": job.company,
                "title": job.title,
                "city": job.city,
                "match_pct": m.match_pct,
                "missing_skills": m.missing,
                "distance_km": round(m.distance_km, 1),
            }
            for m, job in scored
        ],
    }
    return result, {"type": "open_map", "radius_km": radius, "keyword": keyword or None}


def _tool_gap(args: dict[str, Any], profile: Profile) -> tuple[dict[str, Any], dict[str, Any]]:
    role = find_role(str(args.get("role") or profile.target_role or ""))
    gap = career.compute_gap(profile.skills, role.name, profile.location)
    result = {
        "role": gap.role,
        "match_pct": gap.match.match_pct,
        "matched": [m.matched_to for m in gap.match.matched],
        "partial": [m.matched_to for m in gap.match.partial],
        "missing": [s.name for s in gap.match.missing],
        "market_gaps": [
            {"skill": g.skill, "jobs_requiring": g.jobs_requiring, "jobs_total": g.jobs_total} for g in gap.market_gaps[:5]
        ],
    }
    return result, {"type": "open_career_map", "role": gap.role}


def _tool_interview(args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    role = find_role(str(args.get("role") or ""))
    return {"ok": True, "message": f"Opening a mock interview for {role.name}."}, {
        "type": "open_interview",
        "role": role.name,
    }


# --------------------------------------------------------------------------- reply loop

def stream_reply(message: str, history: list[ChatMessage], profile: Profile) -> Iterator[dict[str, Any]]:
    """Answer one user message, calling tools as needed, and yield events for the front end."""
    messages: list[dict[str, Any]] = [{"role": m.role, "content": m.content} for m in history[-HISTORY_TURNS:]]
    messages.append({"role": "user", "content": message})
    system = system_prompt(profile)

    final = ""
    try:
        # Tools stay defined on every round: providers reject tool_use history without a tools list.
        for _ in range(MAX_TOOL_ROUNDS):
            turn = chat(messages, system=system, tools=TOOLS)
            if not turn.tool_calls:
                final = turn.text
                break
            messages.append(
                {"role": "assistant", "content": turn.text, "tool_calls": [c.model_dump() for c in turn.tool_calls]}
            )
            for call in turn.tool_calls:
                result, action = run_tool(call.name, call.arguments, profile)
                if action:
                    yield {**action}
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "name": call.name, "content": json.dumps(result)}
                )
        else:
            final = "I looked up what I could, but I need a more specific question to go further."
    except LLMError as exc:
        yield {"type": "error", "message": str(exc)}
        return

    for piece in _chunks(final):
        yield {"type": "text", "delta": piece}
    yield {"type": "done"}


def _chunks(text: str, size: int = CHUNK_CHARS) -> Iterator[str]:
    """Split text into pieces of about `size` characters on word boundaries, keeping all whitespace."""
    buffer = ""
    for token in re.findall(r"\S+\s*|\s+", text):
        buffer += token
        if len(buffer) >= size:
            yield buffer
            buffer = ""
    if buffer:
        yield buffer
