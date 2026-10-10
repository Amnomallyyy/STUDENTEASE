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
    strength: int = Field(default=0, ge=0, le=3, description="0 absent, 1 vague, 2 clear, 3 specific (numbers, named tools).")


class StarScore(BaseModel):
    situation: StarElement
    task: StarElement
    action: StarElement
    result: StarElement
    source: Literal["llm", "rules"] = Field(
        default="llm", description="'rules' when the LLM was unavailable and the keyword fallback was used."
    )


class VerbalMetrics(BaseModel):
    word_count: int = Field(ge=0)
    duration_s: float = Field(ge=0, description="0 for a typed answer.")
    wpm: float = Field(ge=0, description="0 for a typed answer.")
    pace_band: Literal["slow", "within", "fast", "unknown"] = Field(description="'unknown' for a typed answer.")
    filler_counts: dict[str, int] = Field(default_factory=dict)
    fillers_per_100_words: float = Field(ge=0)
    star: StarScore
    relevance: float | None = Field(
        default=None, ge=0, le=1, description="Embedding cosine between answer and question; None if no embedding model."
    )
    concise: bool
    component_scores: dict[str, float] = Field(
        default_factory=dict,
        description="0-100 per verbal component: star, conciseness, fillers, relevance, pace (absent when not measurable).",
    )


HandAction = Literal[
    "covering_mouth", "touching_face", "touching_head", "fiddling", "restless", "fist", "gesturing", "resting"
]
"""Rule-based hand actions from the hand model. The first six are distracting habits."""


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
    smile: float = Field(ge=0, le=1, description="Smile above the user's neutral face.")
    brow: float = Field(ge=0, le=1, description="Brow lowering above the user's neutral face.")
    nodded: bool = False
    # Added by M4 (all optional, so older payloads still validate). Averaged yaw/pitch per second hides
    # quick glances (left then right averages to "looking at the camera"), so the browser also sends
    # the per-frame share of eye contact, measured against the user's own calibrated baseline.
    eye_contact_frac: float | None = Field(
        default=None, ge=0, le=1, description="Share of this second's frames with head (+/-15 deg) and eyes on the screen, vs the user's baseline."
    )
    face_detected: bool = True
    pose_detected: bool = Field(default=True, description="False when shoulders were not visible; tilt/lean are then 0 and ignored.")
    hands_visible: bool = Field(default=False, description="False when no hand was in frame; wrist_velocity is then ignored.")
    tension: float | None = Field(
        default=None, ge=0, le=1,
        description="Strongest of brow-down / nose-wrinkle / lip-press / mouth-frown above the user's neutral face.",
    )
    hand_action: HandAction | None = Field(default=None, description="Dominant hand action this second; None = no hands seen.")


class NonVerbalMetrics(BaseModel):
    """Per-answer aggregation (services/interview/nonverbal.py)."""

    eye_contact_pct: float = Field(ge=0, le=100)
    head_stability: float = Field(ge=0, description="Variance of nose-tip position; higher = more movement.")
    posture_flags: list[Literal["slouching", "leaning_out_of_frame", "shoulders_tilted"]] = Field(default_factory=list)
    fidget_pct: float = Field(ge=0, le=100, description="Share of seconds with a distracting hand action.")
    expression_label: Literal["neutral", "engaged", "tense"] = "neutral"
    nod_count: int = Field(default=0, ge=0)
    body_language_score: float = Field(ge=0, le=100)
    hand_actions: dict[str, float] = Field(
        default_factory=dict, description="Share of the answer's seconds (0-100) per hand action that occurred."
    )


class AnswerResult(BaseModel):
    question: InterviewQuestion
    transcript: str
    verbal: VerbalMetrics
    non_verbal: NonVerbalMetrics | None = Field(default=None, description="None in verbal-only mode.")
    verbal_score: float = Field(ge=0, le=100)
    rewritten_answer: str = ""
    coaching_notes: list[str] = Field(default_factory=list, description="2-3 concrete, kind body-language notes.")
    content_feedback: list[str] = Field(
        default_factory=list, description="What to fix in the answer itself (missing STAR parts, fillers, length, relevance)."
    )


class InterviewReport(BaseModel):
    role: str
    answers: list[AnswerResult] = Field(default_factory=list)
    verbal_score: float = Field(ge=0, le=100)
    non_verbal_score: float | None = Field(default=None, ge=0, le=100)
    readiness: float = Field(ge=0, le=100, description="0.70 * verbal + 0.30 * non-verbal; equals verbal if no video.")
    verbal_weight: float = 0.70
    non_verbal_weight: float = 0.30
    fix_first: str = Field(default="", description="The single highest-impact thing to improve.")
