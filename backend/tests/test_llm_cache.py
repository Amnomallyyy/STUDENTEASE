"""The LLM_CACHE_PATH short-circuit in complete_json: a recorded reply never reaches a provider."""
import hashlib
import json

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

    def boom(*args, **kwargs):
        raise AssertionError("provider must not be called on a cache hit")

    monkeypatch.setattr(llm_adapter, "_PROVIDERS", {"anthropic": boom})

    assert llm_adapter.complete_json("hello", Answer) == Answer(text="cached")


def test_recording_adds_the_reply_and_keeps_other_keys(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "cached_responses.json"
    monkeypatch.setenv("LLM_CACHE_PATH", str(path))
    monkeypatch.setenv("LLM_CACHE_RECORD", "1")
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
