"""LLM failures become short, safe messages with the right HTTP status (no provider text, org ids or billing links)."""
from __future__ import annotations

import pytest

from backend import llm_adapter
from backend.api.errors import http_error
from backend.llm_adapter import LLMError

GROQ_DAILY_LIMIT = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for model `qwen/qwen3.8-27b` in organization "
    "`org_01m4gdfaa4e9g9r5x5p3azqjhs` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199197, "
    "Requested 2457. Please try again in 11m54.528s. Need more tokens? Upgrade to Dev Tier today at "
    "https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
)


class _Status(Exception):
    def __init__(self, message: str, status_code: int | None = None, code: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def test_daily_rate_limit_gets_a_friendly_message_and_retry_after():
    err = llm_adapter._llm_error("OpenAI", _Status(GROQ_DAILY_LIMIT, 429, "rate_limit_exceeded"))

    assert err.kind == "rate_limit"
    assert err.retry_after_s == pytest.approx(714.528)
    assert err.user_message == "The AI service has reached its usage limit. Please try again in about 12 minutes."

    http = http_error(err)
    assert http.status_code == 429
    assert http.headers == {"Retry-After": "715"}
    for leaked in ("org_", "groq", "billing", "qwen", "tokens"):
        assert leaked not in http.detail


def test_rate_limit_without_a_wait_still_reads_well():
    err = llm_adapter._llm_error("OpenAI", _Status("Error 429 rate_limit", 429))

    assert err.retry_after_s is None
    assert err.user_message.endswith("Please try again in a few minutes.")
    assert http_error(err).headers is None


@pytest.mark.parametrize(
    ("exc", "kind", "status"),
    [
        (_Status("Incorrect API key provided", 401), "auth", 503),
        (_Status("Connection error."), "connection", 503),
        (_Status("Request timed out."), "connection", 503),
        (_Status("Internal server error", 500), "overloaded", 503),
        (_Status("something odd", 400), "unavailable", 502),
    ],
)
def test_provider_errors_are_classified(exc, kind, status):
    err = llm_adapter._llm_error("OpenAI", exc)

    assert err.kind == kind
    assert http_error(err).status_code == status
    assert str(exc) not in err.user_message


def test_missing_key_is_an_auth_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    llm_adapter._compat_client.cache_clear()

    with pytest.raises(LLMError) as info:
        llm_adapter._compat_client("groq")

    assert info.value.kind == "auth"
    assert "GROQ_API_KEY" in str(info.value)  # technical detail stays in the log message
    assert "GROQ_API_KEY" not in info.value.user_message


def test_unreadable_reply_is_an_invalid_output_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_CACHE_PATH", raising=False)
    monkeypatch.setitem(llm_adapter._PROVIDERS, "openai", lambda *a, **k: "not json")

    from pydantic import BaseModel

    class Answer(BaseModel):
        text: str

    with pytest.raises(LLMError) as info:
        llm_adapter.complete_json("hi", Answer, retries=0)

    assert info.value.kind == "invalid_output"
    assert http_error(info.value).status_code == 502
