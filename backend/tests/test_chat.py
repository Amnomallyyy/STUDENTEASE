import json

from backend.llm_adapter import AssistantTurn, LLMError, ToolCall
from backend.schemas import Job, Location, MatchResult, Profile, Role, Skill, SkillCategory, SkillMatch, UserMode
from backend.services import chat as chat_service
from backend.services.data import RoleNotFound


def skill(name: str) -> Skill:
    return Skill(name=name, category=SkillCategory.tool)


def profile() -> Profile:
    return Profile(
        mode=UserMode.job_seeker,
        target_role="Data Analyst",
        location=Location(lat=24.86, lng=67.0, city="Karachi"),
        skills=[skill("Python")],
        gap=MatchResult(
            match_pct=65,
            matched=[SkillMatch(name="Python", matched_to="Python", similarity=1.0)],
            missing=[skill("SQL")],
        ),
        integrity_score=0.0,
    )


def acme_job() -> Job:
    return Job(
        id="j1", company="Acme", title="Python Analyst", city="Karachi", lat=24.87, lng=67.0,
        requirements_text="Python and reporting", required_skills=[skill("Python")],
    )


def script_chat(monkeypatch, turns):
    """Replace the LLM chat call with a scripted sequence of turns. Returns the messages seen on each call."""
    seen = []
    queue = list(turns)

    def fake(messages, **kwargs):
        seen.append([dict(m) for m in messages])
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(chat_service, "chat", fake)
    return seen


def test_context_summarises_the_profile_and_drops_empty_sections():
    ctx = chat_service.build_context(profile())

    assert ctx["mode"] == "job_seeker"
    assert ctx["city"] == "Karachi"
    assert ctx["role_match"] == {"match_pct": 65, "matched": ["Python"], "partial": [], "missing": ["SQL"]}
    assert ctx["integrity_score"] == 0.0  # a real zero is kept
    assert "anomalies" not in ctx and "interview" not in ctx and "roadmap" not in ctx


def test_system_prompt_carries_mode_guidance_and_profile():
    prompt = chat_service.system_prompt(profile())

    assert "job seeker" in prompt
    assert '"target_role": "Data Analyst"' in prompt
    assert "Never invent companies" in prompt


def test_jobs_tool_filters_by_keyword_and_asks_the_ui_to_open_the_map(monkeypatch):
    monkeypatch.setattr(chat_service, "load_jobs", lambda: [acme_job()])

    result, action = chat_service.run_tool("get_jobs_near_me", {"radius_km": 30, "keyword": "Acme"}, profile())

    assert result["jobs_found"] == 1
    assert result["top_matches"][0]["title"] == "Python Analyst"
    assert result["top_matches"][0]["match_pct"] == 100.0
    assert action == {"type": "open_map", "radius_km": 30.0, "keyword": "acme"}


def test_interview_tool_opens_the_interview_screen(monkeypatch):
    monkeypatch.setattr(chat_service, "find_role", lambda name: Role(id="da", name="Data Analyst"))

    result, action = chat_service.run_tool("start_mock_interview", {"role": "data analyst"}, profile())

    assert result["ok"] is True
    assert action == {"type": "open_interview", "role": "Data Analyst"}


def test_tool_errors_become_data_for_the_model_not_exceptions(monkeypatch):
    def unknown(name):
        raise RoleNotFound("Unknown role 'Nope'")

    monkeypatch.setattr(chat_service, "find_role", unknown)

    result, action = chat_service.run_tool("explain_gap", {"role": "Nope"}, profile())

    assert "Unknown role" in result["error"] and action is None
    assert chat_service.run_tool("no_such_tool", {}, profile())[0]["error"].startswith("Unknown tool")


def test_reply_runs_the_tool_then_streams_the_answer(monkeypatch):
    monkeypatch.setattr(chat_service, "find_role", lambda name: Role(id="da", name="Data Analyst"))
    answer = "Opening your interview now.\nGood luck, and remember to use the STAR format."
    seen = script_chat(
        monkeypatch,
        [
            AssistantTurn(tool_calls=[ToolCall(id="t1", name="start_mock_interview", arguments={"role": "Data Analyst"})]),
            AssistantTurn(text=answer),
        ],
    )

    events = list(chat_service.stream_reply("start an interview", [], profile()))

    assert events[0] == {"type": "open_interview", "role": "Data Analyst"}
    assert events[-1] == {"type": "done"}
    assert "".join(e["delta"] for e in events if e["type"] == "text") == answer
    second_call = seen[1]
    assert second_call[-2]["tool_calls"][0]["id"] == "t1"
    assert second_call[-1]["role"] == "tool" and second_call[-1]["tool_call_id"] == "t1"
    assert json.loads(second_call[-1]["content"])["ok"] is True


def test_reply_stops_after_the_tool_round_limit(monkeypatch):
    looping = AssistantTurn(tool_calls=[ToolCall(id="t", name="no_such_tool", arguments={})])
    seen = script_chat(monkeypatch, [looping])

    events = list(chat_service.stream_reply("hi", [], profile()))

    assert len(seen) == chat_service.MAX_TOOL_ROUNDS
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "text" for e in events)


def test_llm_failure_becomes_an_error_event(monkeypatch):
    def boom(messages, **kwargs):
        raise LLMError("provider down")

    monkeypatch.setattr(chat_service, "chat", boom)

    events = list(chat_service.stream_reply("hi", [], profile()))

    assert events == [{"type": "error", "message": "provider down"}]


def test_chunks_keep_all_text():
    text = "Line one has  two spaces.\nLine two is here, and a third sentence follows it closely."

    chunks = list(chat_service._chunks(text))

    assert "".join(chunks) == text
    assert len(chunks) > 1
