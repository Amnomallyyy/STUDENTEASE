"""The only module that talks to an LLM or embedding model. Everything else calls these two functions:

    complete_json(prompt, schema)  -> validated instance of a Pydantic model
    embed(texts)                   -> list of unit-length vectors

Provider switch (env vars, all optional):
    LLM_PROVIDER     anthropic (default) | openai | ollama
    EMBED_PROVIDER   local (default, sentence-transformers) | openai
    ANTHROPIC_API_KEY / ANTHROPIC_MODEL
    OPENAI_API_KEY / OPENAI_MODEL / OPENAI_EMBED_MODEL
    OLLAMA_HOST / OLLAMA_MODEL
    EMBED_MODEL      local model name (default all-MiniLM-L6-v2, 384-dim)
"""
from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError

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

    json_schema = schema.model_json_schema()
    feedback = ""
    last_error: Exception | None = None
    for _ in range(retries + 1):
        raw = call(prompt + feedback, json_schema, schema.__name__, system, temperature, max_tokens)
        try:
            data = raw if isinstance(raw, dict) else json.loads(raw)
            return schema.model_validate(data)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            feedback = f"\n\nYour previous reply was invalid ({exc}). Reply again with JSON that matches the schema exactly."
    raise LLMError(f"No schema-valid reply from {provider} after {retries + 1} attempts: {last_error}") from last_error


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
