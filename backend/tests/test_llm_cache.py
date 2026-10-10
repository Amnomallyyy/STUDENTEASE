"""The LLM_CACHE_PATH short-circuit in complete_json: a recorded reply never reaches a provider."""
import hashlib
import json

import pytest
from pydantic import BaseModel

from backend import llm_adapter


class Answer(BaseModel):
    text: str


def key_for(prompt: str) -> str:
    return hashlib.sha256(f"Answer\n{prompt}".encode("utf-8")).hexdigest()


def test_cached_reply_skips_the_provider(tmp_path, monkeypatch):
    path = tmp_path / "cached_responses.json"
    path.write_text(json.dumps({"github": {}, "llm": {key_for("hello"): {"text": "cached"}}}), encoding="utf-8")
    monkeypatch.setenv("LLM_CACHE_PATH", str(path))
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")  # the developer's .env may select another provider

    def boom(*args, **kwargs):
        raise AssertionError("provider must not be called on a cache hit")

    monkeypatch.setattr(llm_adapter, "_PROVIDERS", {"anthropic": boom})

    assert llm_adapter.complete_json("hello", Answer) == Answer(text="cached")


def test_recording_adds_the_reply_and_keeps_other_keys(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "cached_responses.json"
    monkeypatch.setenv("LLM_CACHE_PATH", str(path))
    monkeypatch.setenv("LLM_CACHE_RECORD", "1")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    calls = []

    def provider(prompt, *args):
        calls.append(prompt)
        return {"text": "live"}

    monkeypatch.setattr(llm_adapter, "_PROVIDERS", {"anthropic": provider})

    assert llm_adapter.complete_json("hello", Answer) == Answer(text="live")
    assert json.loads(path.read_text(encoding="utf-8")) == {"llm": {key_for("hello"): {"text": "live"}}}

    path.write_text(json.dumps({"github": {"demo": {}}, "llm": {}}), encoding="utf-8")
    llm_adapter.complete_json("again", Answer)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["github"] == {"demo": {}} and key_for("again") in stored["llm"]

    monkeypatch.delenv("LLM_CACHE_RECORD")
    assert llm_adapter.complete_json("again", Answer) == Answer(text="live")  # now served from the file
    assert calls == ["hello", "again"]

def test_openai_json_mode_failure_retries_without_json_mode(monkeypatch):
    class Boom(Exception):
        code = "json_validate_failed"

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if "response_format" in kwargs:
                raise Boom("Error code: 400 - Failed to validate JSON. Please adjust your prompt.")
            message = type("M", (), {"content": 'Here you go:\n```json\n{"text": "recovered"}\n```'})()
            return type("R", (), {"choices": [type("C", (), {"message": message})()]})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    monkeypatch.setattr(llm_adapter, "_openai_client", lambda: client)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-120b")
    monkeypatch.delenv("LLM_CACHE_PATH", raising=False)

    assert llm_adapter.complete_json("hello", Answer, max_tokens=100) == Answer(text="recovered")
    assert [c.get("max_tokens") for c in calls] == [100, 200]  # retry doubles the budget
    assert "response_format" not in calls[1]
    assert calls[0]["extra_body"] == {"reasoning_effort": "low"}  # gpt-oss gets low reasoning effort


def test_openai_other_errors_are_not_retried(monkeypatch):
    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("rate limit")

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    monkeypatch.setattr(llm_adapter, "_openai_client", lambda: client)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("LLM_CACHE_PATH", raising=False)

    with pytest.raises(llm_adapter.LLMError):
        llm_adapter.complete_json("hello", Answer, retries=0)
    assert len(calls) == 1 and "extra_body" not in calls[0]  # no reasoning knob for ordinary models

def test_openai_rate_limit_falls_back_to_the_smaller_model(monkeypatch):
    class Limited(Exception):
        code = "rate_limit_exceeded"
        status_code = 429

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if kwargs["model"] == "openai/gpt-oss-120b":
                raise Limited("Error code: 429 - Rate limit reached ... tokens per day")
            message = type("M", (), {"content": '{"text": "from fallback"}'})()
            return type("R", (), {"choices": [type("C", (), {"message": message})()]})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    monkeypatch.setattr(llm_adapter, "_openai_client", lambda: client)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-120b")
    monkeypatch.delenv("OPENAI_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("LLM_CACHE_PATH", raising=False)

    assert llm_adapter.complete_json("hello", Answer) == Answer(text="from fallback")
    assert [c["model"] for c in calls] == ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

    monkeypatch.setenv("OPENAI_FALLBACK_MODEL", "openai/gpt-oss-120b")  # same model: no retry, error surfaces
    calls.clear()
    with pytest.raises(llm_adapter.LLMError):
        llm_adapter.complete_json("hello", Answer, retries=0)
    assert len(calls) == 1
