"""The only module that talks to an LLM or embedding model. Everything else calls these functions:

    complete_json(prompt, schema)  -> validated instance of a Pydantic model
    chat(messages, tools=...)      -> one chat turn, with optional tool calls (used by the chatbot)
    embed(texts)                   -> list of unit-length vectors

Provider switch (env vars, all optional):
    LLM_PROVIDER     anthropic (default) | openai | groq | deepseek | grok | ollama
    EMBED_PROVIDER   local (default, sentence-transformers) | openai
    ANTHROPIC_API_KEY / ANTHROPIC_MODEL
    OPENAI_API_KEY / OPENAI_MODEL / OPENAI_EMBED_MODEL / OPENAI_BASE_URL (any OpenAI-compatible host)
    GROQ_API_KEY / GROQ_MODEL          (GroqCloud, free tier, default openai/gpt-oss-120b)
    DEEPSEEK_API_KEY / DEEPSEEK_MODEL  (default deepseek-flash)
    XAI_API_KEY / XAI_MODEL            (Grok, default grok-4.3)
    groq / deepseek / grok are shortcuts for the OpenAI-compatible path with their own key, URL and model;
    they get the same rate-limit fallback, JSON-mode retry and reasoning_effort handling as openai.
    OLLAMA_HOST / OLLAMA_MODEL
    EMBED_MODEL      local model name (default all-MiniLM-L6-v2, 384-dim)
    LLM_CACHE_PATH   JSON file of recorded complete_json replies, {"llm": {sha256(schema + prompt): result}};
                     a hit is returned without calling a provider (offline demo insurance)
    LLM_CACHE_RECORD set to 1 to add every successful complete_json reply to LLM_CACHE_PATH
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from functools import lru_cache, partial
from pathlib import Path
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field, ValidationError

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"

# OpenAI-compatible providers other than OpenAI itself: (API key env var, base URL, model env var, default model).
OPENAI_COMPATIBLE: dict[str, tuple[str, str, str, str]] = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_MODEL", "openai/gpt-oss-120b"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com", "DEEPSEEK_MODEL", "deepseek-flash"),
    "grok": ("XAI_API_KEY", "https://api.x.ai/v1", "XAI_MODEL", "grok-4.3"),
}
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class LLMError(RuntimeError):
    """Raised when a provider call fails or never returns output that matches the schema.

    `str(exc)` is the technical message (for logs and tests). `user_message` is safe to show in the UI: it
    never contains the provider's raw reply, which can carry organisation ids, model names and billing links.
    `kind` is one of rate_limit | auth | connection | overloaded | invalid_output | unavailable.
    """

    def __init__(self, message: str, *, kind: str = "unavailable", retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.retry_after_s = retry_after_s

    @property
    def user_message(self) -> str:
        if self.kind == "rate_limit":
            return f"The AI service has reached its usage limit. Please try again {_wait_phrase(self.retry_after_s)}."
        if self.kind == "auth":
            return "The AI service is not set up correctly (its API key is missing or was rejected). Please tell the site owner."
        if self.kind == "connection":
            return "Could not reach the AI service. Check your internet connection and try again."
        if self.kind == "overloaded":
            return "The AI service is busy right now. Please try again in a minute."
        if self.kind == "invalid_output":
            return "The AI service sent back an answer that could not be read. Please try again."
        return "The AI service is unavailable right now. Please try again shortly."

    @property
    def http_status(self) -> int:
        return {"rate_limit": 429, "auth": 503, "connection": 503, "overloaded": 503}.get(self.kind, 502)


def _wait_phrase(seconds: float | None) -> str:
    """'in about 12 minutes' / 'in 30 seconds' / 'later' when the provider gave no wait."""
    if seconds is None:
        return "in a few minutes"
    seconds = max(1, math.ceil(seconds))
    if seconds < 90:
        return f"in {seconds} seconds"
    minutes = math.ceil(seconds / 60)
    if minutes < 90:
        return f"in about {minutes} minutes"
    return f"in about {math.ceil(minutes / 60)} hours"


def _llm_error(provider: str, exc: Exception) -> LLMError:
    """Turn a provider SDK exception into an LLMError with a kind, logging the raw detail once."""
    text = f"{type(exc).__name__} {getattr(exc, 'code', '')} {getattr(exc, 'status_code', '')} {exc}"
    lowered = text.lower()
    status = getattr(exc, "status_code", None)
    if _is_rate_limit(exc):
        kind = "rate_limit"
    elif status in (401, 403) or "authentication" in lowered or "invalid api key" in lowered or "permission" in lowered:
        kind = "auth"
    elif "timeout" in lowered or "connection" in lowered or "timed out" in lowered:
        kind = "connection"
    elif (isinstance(status, int) and status >= 500) or "overloaded" in lowered:
        kind = "overloaded"
    else:
        kind = "unavailable"
    log.warning("%s call failed (%s): %s", provider, kind, exc)
    return LLMError(f"{provider} call failed: {exc}", kind=kind, retry_after_s=_retry_after(exc) if kind == "rate_limit" else None)


# --------------------------------------------------------------------------- structured output

def complete_json(
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    retries: int = 1,
) -> T:
    """Run one LLM call and return the reply parsed into `schema`.

    On a validation failure the error is fed back to the model and the call is retried
    up to `retries` times. `temperature` is applied by providers that accept it; the
    Anthropic path relies on a forced tool call for stable output instead.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    call = _PROVIDERS.get(provider)
    if call is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use one of: {', '.join(_PROVIDERS)}.")

    cache_key = hashlib.sha256(f"{schema.__name__}\n{prompt}".encode("utf-8")).hexdigest()
    cached = _cache_read(cache_key)
    if cached is not None:
        return schema.model_validate(cached)

    json_schema = schema.model_json_schema()
    feedback = ""
    last_error: Exception | None = None
    for _ in range(retries + 1):
        raw = call(prompt + feedback, json_schema, schema.__name__, system, temperature, max_tokens)
        try:
            data = raw if isinstance(raw, dict) else json.loads(raw)
            result = schema.model_validate(data)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            feedback = f"\n\nYour previous reply was invalid ({exc}). Reply again with JSON that matches the schema exactly."
            continue
        _cache_write(cache_key, result)
        return result
    raise LLMError(
        f"No schema-valid reply from {provider} after {retries + 1} attempts: {last_error}", kind="invalid_output"
    ) from last_error


def _cache_read(key: str) -> dict[str, Any] | None:
    """A recorded reply from LLM_CACHE_PATH, or None (unset, missing file, bad JSON, or unknown key)."""
    path = os.getenv("LLM_CACHE_PATH")
    if not path or not Path(path).is_file():
        return None
    try:
        entry = json.loads(Path(path).read_text(encoding="utf-8")).get("llm", {}).get(key)
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return entry if isinstance(entry, dict) else None


def _cache_write(key: str, result: BaseModel) -> None:
    """With LLM_CACHE_RECORD=1, store the reply under llm[key], keeping the file's other top-level keys."""
    path = os.getenv("LLM_CACHE_PATH")
    if not path or os.getenv("LLM_CACHE_RECORD") != "1":
        return
    file = Path(path)
    store: dict[str, Any] = {}
    if file.is_file():
        try:
            store = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            store = {}
    store.setdefault("llm", {})[key] = result.model_dump(mode="json")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(store, indent=1), encoding="utf-8")


def _anthropic(prompt, json_schema, name, system, temperature, max_tokens) -> dict[str, Any]:
    client = _anthropic_client()
    kwargs: dict[str, Any] = {
        "model": os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        "max_tokens": max_tokens,
        "tools": [{"name": name, "description": "Return the structured result.", "input_schema": json_schema}],
        "tool_choice": {"type": "tool", "name": name},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    try:
        response = client.messages.create(**kwargs)
    except Exception as exc:  # network, auth, rate limit
        raise _llm_error("Anthropic", exc) from exc
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise LLMError("Anthropic reply contained no tool_use block.", kind="invalid_output")


def _openai_extra(model: str) -> dict[str, Any]:
    """Provider-specific knobs. Reasoning models on OpenAI-compatible hosts (Groq's gpt-oss) spend the token
    budget on hidden reasoning before the JSON; `reasoning_effort=low` keeps the answer inside max_tokens."""
    effort = os.getenv("OPENAI_REASONING_EFFORT") or ("low" if "gpt-oss" in model else None)
    return {"extra_body": {"reasoning_effort": effort}} if effort else {}


def _is_rate_limit(exc: Exception) -> bool:
    """HTTP 429 from the host (Groq's free tier has per-minute and per-day token caps per model)."""
    text = f"{getattr(exc, 'code', '')} {getattr(exc, 'status_code', '')} {exc}"
    return "rate_limit" in text or "429" in text


RETRY_WAIT_MAX_S = 20.0  # a per-minute cap says "try again in 8.7s": worth waiting; a per-day cap says minutes: not
_RETRY_AFTER = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.IGNORECASE)
# Groq counts the daily token cap per model, so each extra model is more free quota. Best first; every model here
# supports JSON mode and tool calling (the chatbot and the interview scoring need both).
_GROQ_CHAIN = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
_DEFAULT_FALLBACKS = {model: _GROQ_CHAIN[i + 1 :] for i, model in enumerate(_GROQ_CHAIN[:-1])}


def _retry_after(exc: Exception) -> float | None:
    """Seconds the host asked us to wait, parsed from Groq's message, or None."""
    match = _RETRY_AFTER.search(str(exc))
    if not match:
        return None
    minutes, seconds = match.groups()
    return (int(minutes) * 60 if minutes else 0) + float(seconds)


def _fallback_models(model: str) -> list[str]:
    """Models to try, in order, when `model` is rate-limited: OPENAI_FALLBACK_MODEL (comma-separated) or
    Groq's smaller models for gpt-oss."""
    configured = os.getenv("OPENAI_FALLBACK_MODEL")
    chain = [m.strip() for m in configured.split(",") if m.strip()] if configured else _DEFAULT_FALLBACKS.get(model, [])
    return [m for m in chain if m != model]


def _fallback_model(model: str) -> str | None:
    """The first fallback (kept for callers and tests that expect a single model)."""
    chain = _fallback_models(model)
    return chain[0] if chain else None


def _create_with_fallback(client: Any, kwargs: dict[str, Any]) -> Any:
    """chat.completions.create with Groq-style resilience: on a 429 that names a short wait, sleep and retry
    the same model once; otherwise move down the fallback chain. Any other error surfaces at once."""
    models = [kwargs["model"], *_fallback_models(kwargs["model"])]
    last: Exception | None = None
    for model in models:
        attempt = {**kwargs, "model": model, **_openai_extra(model)}
        try:
            return client.chat.completions.create(**attempt)
        except Exception as exc:
            if not _is_rate_limit(exc):
                raise
            last = exc
            wait = _retry_after(exc)
            if wait is not None and wait <= RETRY_WAIT_MAX_S:
                time.sleep(wait + 0.5)
                try:
                    return client.chat.completions.create(**attempt)
                except Exception as again:
                    if not _is_rate_limit(again):
                        raise
                    last = again
    assert last is not None
    raise last


def _is_json_mode_failure(exc: Exception) -> bool:
    """Groq returns 400 `json_validate_failed` when the model's output is not valid JSON (often truncated)."""
    text = f"{getattr(exc, 'code', '')} {exc}"
    return "json_validate_failed" in text or "Failed to validate JSON" in text


def _json_object(text: str) -> str:
    """The first {...} block of a reply that may carry prose or a ```json fence around the object."""
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start >= 0 and end > start else text


def _openai(prompt, json_schema, name, system, temperature, max_tokens, provider: str = "openai") -> str:
    client = _client_for(provider)
    model = _model_for(provider)
    sys_msg = (system + "\n\n" if system else "") + (
        "Reply with a single JSON object that matches this JSON Schema, and nothing else:\n"
        + json.dumps(json_schema)
    )
    messages = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, **_openai_extra(model)}
    try:
        response = _create_with_fallback(client, {**kwargs, "response_format": {"type": "json_object"}, "max_tokens": max_tokens})
    except Exception as exc:
        if not _is_json_mode_failure(exc):
            raise _llm_error("OpenAI", exc) from exc
        # The host rejected the model's own JSON: ask again with twice the budget and no JSON mode, then
        # cut the object out of the text ourselves (complete_json still validates it against the schema).
        try:
            response = _create_with_fallback(client, {**kwargs, "max_tokens": max_tokens * 2})
        except Exception as retry_exc:
            raise _llm_error("OpenAI", retry_exc) from retry_exc
        return _json_object(response.choices[0].message.content or "")
    return response.choices[0].message.content or ""


def _ollama(prompt, json_schema, name, system, temperature, max_tokens) -> str:
    import requests

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    try:
        resp = requests.post(
            f"{host}/api/chat",
            json={
                "model": os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
                "messages": messages,
                "format": json_schema,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as exc:
        err = _llm_error("Ollama", exc)
        if err.kind == "unavailable" and "connection" not in str(exc).lower():
            err.kind = "connection"  # Ollama is local: a failed call almost always means it is not running
        raise err from exc
    return resp.json()["message"]["content"]


_PROVIDERS: dict[str, Callable[..., Any]] = {
    "anthropic": _anthropic,
    "openai": _openai,
    **{name: partial(_openai, provider=name) for name in OPENAI_COMPATIBLE},
    "xai": partial(_openai, provider="grok"),
    "ollama": _ollama,
}


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


@lru_cache(maxsize=1)
def _openai_client():
    import openai

    return openai.OpenAI()  # reads OPENAI_API_KEY (and OPENAI_BASE_URL for another OpenAI-compatible host)


@lru_cache(maxsize=None)
def _compat_client(provider: str):
    """OpenAI SDK client for groq / deepseek / grok, with that provider's key and base URL."""
    key_env, base_url, _, _ = OPENAI_COMPATIBLE[provider]
    key = os.getenv(key_env, "").strip()
    if not key:
        raise LLMError(f"{key_env} is not set (LLM_PROVIDER={provider}). Add it to .env.", kind="auth")
    try:
        import openai
    except ImportError as exc:
        raise LLMError("The 'openai' package is not installed: pip install -r backend/requirements.txt") from exc
    return openai.OpenAI(api_key=key, base_url=base_url)


def _client_for(provider: str):
    return _openai_client() if provider == "openai" else _compat_client(provider)


def _model_for(provider: str) -> str:
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    _, _, model_env, default = OPENAI_COMPATIBLE[provider]
    return os.getenv(model_env, default)


# --------------------------------------------------------------------------- chat with tools

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AssistantTurn(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


def chat(
    messages: list[dict[str, Any]],
    *,
    system: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> AssistantTurn:
    """One chat turn, with optional tool calling, in a provider-neutral format.

    messages: {"role": "user"|"assistant"|"tool", "content": str, ...}. An assistant message may carry
    "tool_calls": [{"id", "name", "arguments"}]; a tool message carries "tool_call_id" and "name".
    tools: [{"name", "description", "parameters": <JSON Schema>}].
    The Ollama path ignores `tools` (small local models are unreliable at them): it only answers in text.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    call = _CHAT_PROVIDERS.get(provider)
    if call is None:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use one of: {', '.join(_CHAT_PROVIDERS)}.")
    return call(messages, system, tools, max_tokens, temperature)


def _anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            last = out[-1] if out else None
            if last and last["role"] == "user" and isinstance(last["content"], list) and last["content"][0].get("type") == "tool_result":
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        elif m["role"] == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for c in m.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c.get("arguments") or {}})
            out.append({"role": "assistant", "content": blocks or m.get("content", "")})
        else:
            out.append({"role": "user", "content": m["content"]})
    return out


def _anthropic_chat(messages, system, tools, max_tokens, temperature) -> AssistantTurn:
    client = _anthropic_client()
    kwargs: dict[str, Any] = {
        "model": os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL),
        "max_tokens": max_tokens,
        "messages": _anthropic_messages(messages),
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = [
            {"name": t["name"], "description": t.get("description", ""), "input_schema": t["parameters"]} for t in tools
        ]
    try:
        response = client.messages.create(**kwargs)
    except Exception as exc:
        raise _llm_error("Anthropic", exc) from exc
    text = "".join(b.text for b in response.content if b.type == "text")
    calls = [ToolCall(id=b.id, name=b.name, arguments=dict(b.input)) for b in response.content if b.type == "tool_use"]
    return AssistantTurn(text=text, tool_calls=calls)


def _openai_chat(messages, system, tools, max_tokens, temperature, provider: str = "openai") -> AssistantTurn:
    client = _client_for(provider)
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        if m["role"] == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
            if m.get("tool_calls"):
                entry["tool_calls"] = [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c.get("arguments") or {})}}
                    for c in m["tool_calls"]
                ]
            msgs.append(entry)
        elif m["role"] == "tool":
            msgs.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        else:
            msgs.append({"role": m["role"], "content": m["content"]})
    model = _model_for(provider)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **_openai_extra(model),
    }
    if tools:
        kwargs["tools"] = [
            {"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t["parameters"]}}
            for t in tools
        ]
    try:
        response = _create_with_fallback(client, kwargs)
    except Exception as exc:
        raise _llm_error("OpenAI", exc) from exc
    message = response.choices[0].message
    calls = [
        ToolCall(id=c.id, name=c.function.name, arguments=_loads_object(c.function.arguments))
        for c in (message.tool_calls or [])
    ]
    return AssistantTurn(text=message.content or "", tool_calls=calls)


def _ollama_chat(messages, system, tools, max_tokens, temperature) -> AssistantTurn:
    import requests

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        if m["role"] == "tool":
            msgs.append({"role": "user", "content": f"[result of {m.get('name', 'tool')}] {m['content']}"})
        elif m.get("content"):
            msgs.append({"role": m["role"], "content": m["content"]})
    try:
        resp = requests.post(
            f"{host}/api/chat",
            json={
                "model": os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
                "messages": msgs,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as exc:
        err = _llm_error("Ollama", exc)
        if err.kind == "unavailable" and "connection" not in str(exc).lower():
            err.kind = "connection"
        raise err from exc
    return AssistantTurn(text=resp.json()["message"]["content"])


def _loads_object(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


_CHAT_PROVIDERS: dict[str, Callable[..., AssistantTurn]] = {
    "anthropic": _anthropic_chat,
    "openai": _openai_chat,
    **{name: partial(_openai_chat, provider=name) for name in OPENAI_COMPATIBLE},
    "xai": partial(_openai_chat, provider="grok"),
    "ollama": _ollama_chat,
}


# --------------------------------------------------------------------------- embeddings

def embed(texts: list[str]) -> list[list[float]]:
    """Return one unit-length vector per input text, so cosine similarity is a plain dot product."""
    if not texts:
        return []
    provider = os.getenv("EMBED_PROVIDER", "local").lower()
    if provider == "openai":
        try:
            response = _openai_client().embeddings.create(
                model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"), input=texts
            )
        except Exception as exc:
            raise _llm_error("OpenAI embeddings", exc) from exc
        return [_normalise(item.embedding) for item in response.data]
    if provider == "local":
        vectors = _local_embedder().encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
    raise LLMError(f"Unknown EMBED_PROVIDER '{provider}'. Use 'local' or 'openai'.")


@lru_cache(maxsize=1)
def _local_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL))


def _normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]
