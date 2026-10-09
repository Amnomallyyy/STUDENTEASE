"""Interview session and metrics contract.

Producer: M3. M4 supplies the non-verbal fields (NonVerbalSample / NonVerbalMetrics).
Consumers: M2 (report view), M1 (chat, profile).
Video never reaches the backend: only the per-second numbers below.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    id: str
    text: str
    kind: Literal["behavioural", "technical", "situational"] = "behavioural"


class StarElement(BaseModel):
    present: bool
    evidence_span: str = Field(
        default="",
        description="Quote from the transcript. Empty means the element is not present (no hallucinated Result).",
    )


class StarScore(BaseModel):
    situation: StarElement
    task: StarElement
    action: StarElement
    result: StarElement


class VerbalMetrics(BaseModel):
    word_count: int = Field(ge=0)
    duration_s: float = Field(ge=0)
    wpm: float = Field(ge=0)
    pace_band: Literal["slow", "within", "fast"]
    filler_counts: dict[str, int] = Field(default_factory=dict)
    fillers_per_100_words: float = Field(ge=0)
    star: StarScore
    relevance: float = Field(ge=0, le=1, description="Embedding cosine between answer and question.")
    concise: bool


class NonVerbalSample(BaseModel):
    """One second of browser-side vision output (M4 -> M3)."""

    t: int = Field(ge=0, description="Seconds since the answer started.")
    head_yaw_deg: float
    head_pitch_deg: float
    nose_x: float
    nose_y: float
    shoulder_tilt_deg: float
    forward_lean: float
    wrist_velocity: float = Field(ge=0)
    smile: float = Field(ge=0, le=1)
    brow: float = Field(ge=0, le=1)
    nodded: bool = False


class NonVerbalMetrics(BaseModel):
    """Per-answer aggregation (services/interview/nonverbal.py)."""

    eye_contact_pct: float = Field(ge=0, le=100)
    head_stability: float = Field(ge=0, description="Variance of nose-tip position; higher = more movement.")
    posture_flags: list[Literal["slouching", "leaning_out_of_frame", "shoulders_tilted"]] = Field(default_factory=list)
    fidget_pct: float = Field(ge=0, le=100)
    expression_label: Literal["neutral", "engaged", "tense"] = "neutral"
    nod_count: int = Field(default=0, ge=0)
    body_language_score: float = Field(ge=0, le=100)


class AnswerResult(BaseModel):
    question: InterviewQuestion
    transcript: str
    verbal: VerbalMetrics
    non_verbal: NonVerbalMetrics | None = Field(default=None, description="None in verbal-only mode.")
    verbal_score: float = Field(ge=0, le=100)
    rewritten_answer: str = ""
    coaching_notes: list[str] = Field(default_factory=list, description="2-3 concrete, kind notes.")


class InterviewReport(BaseModel):
    role: str
    answers: list[AnswerResult] = Field(default_factory=list)
    verbal_score: float = Field(ge=0, le=100)
    non_verbal_score: float | None = Field(default=None, ge=0, le=100)
    readiness: float = Field(ge=0, le=100, description="0.70 * verbal + 0.30 * non-verbal; equals verbal if no video.")
    verbal_weight: float = 0.70
    non_verbal_weight: float = 0.30
    fix_first: str = Field(default="", description="The single highest-impact thing to improve.")
