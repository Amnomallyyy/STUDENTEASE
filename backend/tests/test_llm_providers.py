"""OpenAI-compatible providers (DeepSeek, Grok) go through the OpenAI SDK with their own key, URL and model.
No network: the SDK client is replaced by a fake that records how it was built and called."""
import json
import sys
import types

import pytest
from pydantic import BaseModel

from backend import llm_adapter


class Answer(BaseModel):
    value: int


class _FakeOpenAI:
    created: list[dict] = []
    calls: list[dict] = []

    def __init__(self, api_key=None, base_url=None):
        _FakeOpenAI.created.append({"api_key": api_key, "base_url": base_url})
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        _FakeOpenAI.calls.append(kwargs)
        message = types.SimpleNamespace(content=json.dumps({"value": 7}), tool_calls=None)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


@pytest.fixture
def fake_openai(monkeypatch):
    _FakeOpenAI.created, _FakeOpenAI.calls = [], []
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAI))
    llm_adapter._compat_client.cache_clear()
    for var in ("DEEPSEEK_API_KEY", "XAI_API_KEY", "GROQ_API_KEY", "DEEPSEEK_MODEL", "XAI_MODEL", "LLM_CACHE_PATH"):
        monkeypatch.delenv(var, raising=False)
    yield _FakeOpenAI
    llm_adapter._compat_client.cache_clear()


@pytest.mark.parametrize(
    ("provider", "key_env", "base_url", "model"),
    [
        ("deepseek", "DEEPSEEK_API_KEY", "https://api.deepseek.com", "deepseek-flash"),
        ("grok", "XAI_API_KEY", "https://api.x.ai/v1", "grok-4.3"),
        ("xai", "XAI_API_KEY", "https://api.x.ai/v1", "grok-4.3"),
        ("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    ],
)
def test_complete_json_uses_the_provider(monkeypatch, fake_openai, provider, key_env, base_url, model):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv(key_env, "test-key")
    assert llm_adapter.complete_json("Give me a number as JSON.", Answer).value == 7
    assert fake_openai.created == [{"api_key": "test-key", "base_url": base_url}]
    assert fake_openai.calls[0]["model"] == model
    assert fake_openai.calls[0]["response_format"] == {"type": "json_object"}


def test_model_can_be_overridden(monkeypatch, fake_openai):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    llm_adapter.complete_json("JSON please", Answer)
    assert fake_openai.calls[0]["model"] == "deepseek-v4-pro"


def test_chat_uses_the_provider(monkeypatch, fake_openai):
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    monkeypatch.setenv("XAI_API_KEY", "k")
    llm_adapter.chat([{"role": "user", "content": "hi"}], system="be brief")
    assert fake_openai.calls[0]["model"] == "grok-4.3"
    assert fake_openai.created[0]["base_url"] == "https://api.x.ai/v1"


def test_missing_key_is_an_llm_error_so_features_fall_back(monkeypatch, fake_openai):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    with pytest.raises(llm_adapter.LLMError, match="DEEPSEEK_API_KEY is not set"):
        llm_adapter.complete_json("JSON", Answer)


def test_gpt_oss_gets_reasoning_headroom(monkeypatch, fake_openai):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    llm_adapter.complete_json("JSON please", Answer, max_tokens=3000)
    call = fake_openai.calls[0]
    assert call["reasoning_effort"] == "low"
    assert call["max_tokens"] == 3000 + llm_adapter.REASONING_HEADROOM


def test_other_models_keep_their_budget(monkeypatch, fake_openai):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    llm_adapter.complete_json("JSON please", Answer, max_tokens=3000)
    assert fake_openai.calls[0]["max_tokens"] == 3000 and "reasoning_effort" not in fake_openai.calls[0]
