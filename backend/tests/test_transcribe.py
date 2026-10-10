"""Whisper transcription: provider choice, the filler-keeping prompt, and the live clip route. No network."""
import sys
import types

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.interview import transcribe


class _FakeOpenAI:
    calls: list[dict] = []

    def __init__(self, api_key=None, base_url=None):
        self.base_url = base_url
        self.audio = types.SimpleNamespace(transcriptions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        _FakeOpenAI.calls.append({"base_url": self.base_url, **kwargs})
        return types.SimpleNamespace(text=" So, um, I fixed it. ")


def _fake(monkeypatch):
    _FakeOpenAI.calls = []
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAI))


def test_groq_whisper_is_used_with_the_filler_prompt(monkeypatch):
    _fake(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("TRANSCRIBE_PROVIDER", raising=False)
    assert transcribe.transcribe(b"audio") == "So, um, I fixed it."
    call = _FakeOpenAI.calls[0]
    assert call["base_url"] == "https://api.groq.com/openai/v1"
    assert call["model"] == "whisper-large-v3-turbo"
    assert "um" in call["prompt"] and call["temperature"] == 0


def test_no_provider_means_no_transcript(monkeypatch):
    for var in ("GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TRANSCRIBE_PROVIDER", "auto")
    monkeypatch.setattr(transcribe, "_local_model", lambda: None)
    assert transcribe.transcribe(b"audio") is None
    assert transcribe.transcribe(b"") is None


def test_live_clip_route(monkeypatch):
    _fake(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    r = TestClient(app).post("/interview/transcribe", files={"audio": ("clip.webm", b"x" * 10, "audio/webm")})
    assert r.status_code == 200 and r.json() == {"text": "So, um, I fixed it."}
    big = TestClient(app).post("/interview/transcribe", files={"audio": ("clip.webm", b"x" * (3 * 1024 * 1024), "audio/webm")})
    assert big.status_code == 413
