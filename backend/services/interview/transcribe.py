"""Final, accurate transcript from the recorded answer audio. Owner: M3.

The browser's Web Speech API gives the live transcript for free; this pass replaces it with Whisper
when one is available. It never fails a request: if no provider works it returns None and the
caller keeps the browser transcript.

TRANSCRIBE_PROVIDER  auto (default) | groq | openai | local | off
    groq:   Whisper on GroqCloud, free tier (needs GROQ_API_KEY; model GROQ_TRANSCRIBE_MODEL,
            default whisper-large-v3-turbo)
    openai: Whisper API (needs OPENAI_API_KEY; model OPENAI_TRANSCRIBE_MODEL, default whisper-1)
    local:  faster-whisper (pip install faster-whisper; model WHISPER_MODEL, default base.en)
    auto:   groq if GROQ_API_KEY is set, else openai if OPENAI_API_KEY is set, else local if
            faster-whisper is installed, else off
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
from functools import lru_cache

log = logging.getLogger(__name__)


def transcribe(audio: bytes, filename: str = "answer.webm") -> str | None:
    if not audio:
        return None
    provider = os.getenv("TRANSCRIBE_PROVIDER", "auto").lower()
    if provider == "off":
        return None
    if provider in ("groq", "auto") and os.getenv("GROQ_API_KEY"):
        text = _whisper_api(audio, filename, "groq")
        if text is not None or provider == "groq":
            return text
    if provider in ("openai", "auto") and os.getenv("OPENAI_API_KEY"):
        text = _whisper_api(audio, filename, "openai")
        if text is not None or provider == "openai":
            return text
    if provider in ("local", "auto"):
        return _local(audio, filename)
    return None


# Whisper tends to tidy speech into what was meant. A prompt written with fillers in it makes it keep
# the "um"s and "uh"s, which the filler score depends on (OpenAI's Whisper prompting guide).
FILLER_PROMPT = "Umm, let me think like, hmm... Okay, here's what I'm, like, thinking. So, uh, I mean, you know, it was, um, basically fine."

# Whisper over an OpenAI-compatible API: (API key env var, base URL, model env var, default model).
_WHISPER_APIS = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_TRANSCRIBE_MODEL", "whisper-large-v3-turbo"),
    "openai": ("OPENAI_API_KEY", None, "OPENAI_TRANSCRIBE_MODEL", "whisper-1"),
}


def _whisper_api(audio: bytes, filename: str, provider: str) -> str | None:
    key_env, base_url, model_env, default_model = _WHISPER_APIS[provider]
    try:
        import openai

        buf = io.BytesIO(audio)
        buf.name = filename  # the API infers the format from the name
        client = openai.OpenAI(api_key=os.getenv(key_env), base_url=base_url)
        result = client.audio.transcriptions.create(
            model=os.getenv(model_env, default_model), file=buf, language="en", prompt=FILLER_PROMPT, temperature=0
        )
        return (result.text or "").strip() or None
    except Exception as exc:  # network, auth, rate limit, unsupported audio
        log.warning("%s Whisper transcription failed: %s", provider, exc)
        return None


def _local(audio: bytes, filename: str) -> str | None:
    model = _local_model()
    if model is None:
        return None
    suffix = os.path.splitext(filename)[1] or ".webm"
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            path = f.name
        segments, _ = model.transcribe(path, language="en", vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip() or None
    except Exception as exc:
        log.warning("faster-whisper transcription failed: %s", exc)
        return None
    finally:
        try:
            os.unlink(path)
        except (OSError, UnboundLocalError):
            pass


@lru_cache(maxsize=1)
def _local_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    return WhisperModel(os.getenv("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
