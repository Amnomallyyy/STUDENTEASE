"""The only module that talks to an LLM or embedding model. Everything else calls these functions:

    complete_json(prompt, schema)  -> validated instance of a Pydantic model
    chat(messages, tools=...)      -> one chat turn, with optional tool calls (used by the chatbot)
    embed(texts)                   -> list of unit-length vectors

Provider switch (env vars, all optional):
    LLM_PROVIDER     anthropic (default) | openai | ollama
    EMBED_PROVIDER   local (default, sentence-transformers) | openai
    ANTHROPIC_API_KEY / ANTHROPIC_MODEL
    OPENAI_API_KEY / OPENAI_MODEL / OPENAI_EMBED_MODEL
    OLLAMA_HOST / OLLAMA_MODEL
    EMBED_MODEL      local model name (default all-MiniLM-L6-v2, 384-dim)
    LLM_CACHE_PATH   JSON file of recorded complete_json replies, {"llm": {sha256(schema + prompt): result}};
                     a hit is returned without calling a provider (offline demo insurance)
    LLM_CACHE_RECORD set to 1 to add every successful complete_json reply to LLM_CACHE_PATH
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field, ValidationError

T = TypeVar("T", bound=BaseModel)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class LLMError(RuntimeError):
    """Raised when a provider call fails or never returns output that matches the schema."""


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
    raise LLMError(f"No schema-valid reply from {provider} after {retries + 1} attempts: {last_error}") from last_error


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
        raise LLMError(f"Anthropic call failed: {exc}") from exc
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise LLMError("Anthropic reply contained no tool_use block.")


def _openai(prompt, json_schema, name, system, temperature, max_tokens) -> str:
    client = _openai_client()
    sys_msg = (system + "\n\n" if system else "") + (
        "Reply with a single JSON object that matches this JSON Schema, and nothing else:\n"
        + json.dumps(json_schema)
    )
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise LLMError(f"OpenAI call failed: {exc}") from exc
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
        raise LLMError(f"Ollama call failed: {exc}") from exc
    return resp.json()["message"]["content"]


_PROVIDERS: dict[str, Callable[..., Any]] = {"anthropic": _anthropic, "openai": _openai, "ollama": _ollama}


@lru_cache(maxsize=1)
def _anthropic_client():
    import anthropic

    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY


@lru_cache(maxsize=1)
def _openai_client():
    import openai

    return openai.OpenAI()  # reads OPENAI_API_KEY


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
        raise LLMError(f"Anthropic call failed: {exc}") from exc
    text = "".join(b.text for b in response.content if b.type == "text")
    calls = [ToolCall(id=b.id, name=b.name, arguments=dict(b.input)) for b in response.content if b.type == "tool_use"]
    return AssistantTurn(text=text, tool_calls=calls)


def _openai_chat(messages, system, tools, max_tokens, temperature) -> AssistantTurn:
    client = _openai_client()
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
    kwargs: dict[str, Any] = {
        "model": os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "messages": msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = [
            {"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t["parameters"]}}
            for t in tools
        ]
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise LLMError(f"OpenAI call failed: {exc}") from exc
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
        raise LLMError(f"Ollama call failed: {exc}") from exc
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
            raise LLMError(f"OpenAI embeddings call failed: {exc}") from exc
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
