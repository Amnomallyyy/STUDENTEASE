"""Non-verbal (body-language) analysis of one interview answer. Owner: M4.

Input is the 1 Hz NonVerbalSample list the browser sends with POST /interview/answer; video never
reaches the backend. Every metric is rule-based on landmark geometry, so each number can be explained.
frontend/src/vision/aggregate.ts runs the same algorithm for the live gauges; the shared fixture in
frontend/src/vision/__fixtures__/ is checked by both test suites so the two cannot drift apart.

How M3 uses this (services/interview/scoring.py):

    metrics = analyze_answer(samples)                      # None in verbal-only mode
    notes = coaching_notes(question, transcript, metrics, samples) if metrics else []
    non_verbal = session_non_verbal_score([a.non_verbal for a in answers])
    readiness = 0.70 * verbal + 0.30 * non_verbal          # or verbal alone when non_verbal is None
"""
from __future__ import annotations

import math
from pathlib import Path
from statistics import median

from pydantic import BaseModel, Field

from backend.llm_adapter import complete_json
from backend.schemas.interview import NonVerbalMetrics, NonVerbalSample

# Same values as frontend/src/vision/thresholds.ts.
EYE_CONTACT_DEG = 15.0
SHOULDER_TILT_DEG = 8.0
SLOUCH_RATIO = 0.8
SLOUCH_NOSE_Y = 0.65
POSTURE_BASELINE_SECONDS = 3
FRAME_MARGIN_X = 0.08
FRAME_MARGIN_Y = 0.05
STABLE_STD = 0.01
UNSTABLE_STD = 0.06
ENGAGED_SMILE = 0.2
TENSE_LEVEL = 0.15
ENGAGED_SHARE = 0.2
TENSE_SHARE = 0.25
TILT_FLAG_SHARE = 0.25
SLOUCH_FLAG_SHARE = 0.25
OUT_OF_FRAME_FLAG_SHARE = 0.15

WEIGHTS = {"eye_contact": 0.35, "posture": 0.25, "fidget": 0.20, "stability": 0.10, "expression": 0.10}
EXPRESSION_SCORES = {"engaged": 100.0, "neutral": 75.0, "tense": 30.0}

# Most distracting first (same order as HAND_ACTION_ORDER in aggregate.ts).
DISTRACTING_ACTIONS = ["covering_mouth", "touching_face", "touching_head", "fiddling", "restless", "fist"]
HAND_ACTION_ORDER = [*DISTRACTING_ACTIONS, "gesturing", "resting"]
HAND_ACTION_TEXT = {
    "covering_mouth": "covering your mouth",
    "touching_face": "touching your face",
    "touching_head": "touching your hair or head",
    "fiddling": "fiddling with your fingers",
    "restless": "moving your hands restlessly",
    "fist": "clenching your fists",
    "gesturing": "open-hand gestures",
    "resting": "hands resting",
}

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "coaching_notes.md"


# --------------------------------------------------------------------------- per-second rules

def eye_contact_frac(s: NonVerbalSample) -> float:
    """Browser-measured share when present; otherwise judged from the averaged head angles."""
    if s.eye_contact_frac is not None:
        return s.eye_contact_frac
    ok = s.face_detected and abs(s.head_yaw_deg) <= EYE_CONTACT_DEG and abs(s.head_pitch_deg) <= EYE_CONTACT_DEG
    return 1.0 if ok else 0.0


def is_out_of_frame(s: NonVerbalSample) -> bool:
    if not s.face_detected:
        return True
    return not (FRAME_MARGIN_X <= s.nose_x <= 1 - FRAME_MARGIN_X and FRAME_MARGIN_Y <= s.nose_y <= 1 - FRAME_MARGIN_Y)


def is_tilted(s: NonVerbalSample) -> bool:
    return s.pose_detected and abs(s.shoulder_tilt_deg) > SHOULDER_TILT_DEG


def is_slouching(s: NonVerbalSample, baseline_lean: float) -> bool:
    """Sunk lower than at the start of the answer, or simply sitting very low in the frame."""
    if s.face_detected and s.nose_y > SLOUCH_NOSE_Y:
        return True
    return s.pose_detected and baseline_lean > 0 and s.forward_lean < SLOUCH_RATIO * baseline_lean


def is_fidget_second(s: NonVerbalSample) -> bool:
    """A second with a distracting hand action (touching face, fiddling, restless hands, fist...)."""
    return s.hand_action in DISTRACTING_ACTIONS


def posture_baseline(samples: list[NonVerbalSample]) -> float:
    """Median lean over the first seconds with shoulders visible: "sitting normally" for this answer."""
    first = [s.forward_lean for s in samples if s.pose_detected][:POSTURE_BASELINE_SECONDS]
    return float(median(first)) if first else 0.0


def expression_label(samples: list[NonVerbalSample]) -> str:
    """Label from the share of face-visible seconds that were tense / smiling (a quarter of the answer
    frowning is enough for "tense"). Older payloads without `tension` fall back to `brow`."""
    faces = [s for s in samples if s.face_detected]
    if not faces:
        return "neutral"
    tense = sum((s.tension if s.tension is not None else s.brow) >= TENSE_LEVEL for s in faces) / len(faces)
    smiling = sum(s.smile >= ENGAGED_SMILE for s in faces) / len(faces)
    if tense >= TENSE_SHARE and tense >= smiling:
        return "tense"
    if smiling >= ENGAGED_SHARE:
        return "engaged"
    return "neutral"


# --------------------------------------------------------------------------- per-answer aggregation

class SubScores(BaseModel):
    """The five 0-100 inputs to body_language_score (shown in the UI weights tooltip)."""

    eye_contact: float
    posture: float
    fidget: float
    stability: float
    expression: float


def analyze_answer(samples: list[NonVerbalSample]) -> NonVerbalMetrics | None:
    """Aggregate one answer's samples. None when there are none (camera off: verbal-only mode)."""
    result = analyze_answer_detailed(samples)
    return result[0] if result else None


def analyze_answer_detailed(samples: list[NonVerbalSample]) -> tuple[NonVerbalMetrics, SubScores] | None:
    n = len(samples)
    if n == 0:
        return None
    faces = [s for s in samples if s.face_detected]

    eye_pct = 100 * _mean([eye_contact_frac(s) for s in samples])
    head_var = _variance([s.nose_x for s in faces]) + _variance([s.nose_y for s in faces])

    base = posture_baseline(samples)
    out = [is_out_of_frame(s) for s in samples]
    tilt = [is_tilted(s) for s in samples]
    slouch = [is_slouching(s, base) for s in samples]
    problem_share = sum(o or t or sl for o, t, sl in zip(out, tilt, slouch)) / n
    flags = []
    if sum(slouch) / n >= SLOUCH_FLAG_SHARE:
        flags.append("slouching")
    if sum(out) / n >= OUT_OF_FRAME_FLAG_SHARE:
        flags.append("leaning_out_of_frame")
    if sum(tilt) / n >= TILT_FLAG_SHARE:
        flags.append("shoulders_tilted")

    fidget_pct = 100 * sum(is_fidget_second(s) for s in samples) / n
    expression = expression_label(samples)
    hand_actions = {}
    for action in HAND_ACTION_ORDER:
        count = sum(s.hand_action == action for s in samples)
        if count:
            hand_actions[action] = _round(100 * count / n, 1)
    nods = sum(1 for i, s in enumerate(samples) if s.nodded and not (i > 0 and samples[i - 1].nodded))

    subs = SubScores(
        eye_contact=_clamp(eye_pct, 0, 100),
        posture=100 * _clamp(1 - problem_share, 0, 1),
        fidget=_clamp(100 - fidget_pct, 0, 100),
        stability=stability_score(head_var),
        expression=EXPRESSION_SCORES[expression],
    )
    metrics = NonVerbalMetrics(
        eye_contact_pct=_round(eye_pct, 1),
        head_stability=_round(head_var, 6),
        posture_flags=flags,
        fidget_pct=_round(fidget_pct, 1),
        expression_label=expression,
        nod_count=nods,
        body_language_score=weighted_score(subs),
        hand_actions=hand_actions,
    )
    return metrics, subs


def stability_score(head_variance: float) -> float:
    std = math.sqrt(max(0.0, head_variance))
    return 100 * _clamp(1 - (std - STABLE_STD) / (UNSTABLE_STD - STABLE_STD), 0, 1)


def weighted_score(s: SubScores) -> float:
    total = (
        WEIGHTS["eye_contact"] * s.eye_contact
        + WEIGHTS["posture"] * s.posture
        + WEIGHTS["fidget"] * s.fidget
        + WEIGHTS["stability"] * s.stability
        + WEIGHTS["expression"] * s.expression
    )
    return _round(_clamp(total, 0, 100), 1)


def session_non_verbal_score(answers: list[NonVerbalMetrics | None]) -> float | None:
    """Mean body-language score over the answers that had video; None if none did."""
    scores = [a.body_language_score for a in answers if a is not None]
    return _round(_mean(scores), 1) if scores else None


# --------------------------------------------------------------------------- coaching notes

def look_away_spans(samples: list[NonVerbalSample], min_seconds: int = 2) -> list[tuple[int, int]]:
    """Runs of consecutive seconds with eye contact below 50%, as (start_s, end_s) inclusive."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    prev_t: int | None = None
    for s in samples:
        away = eye_contact_frac(s) < 0.5
        if away and start is None:
            start = s.t
        if not away and start is not None:
            if prev_t is not None and prev_t - start + 1 >= min_seconds:
                spans.append((start, prev_t))
            start = None
        prev_t = s.t
    if start is not None and prev_t is not None and prev_t - start + 1 >= min_seconds:
        spans.append((start, prev_t))
    return spans


class CoachingNotes(BaseModel):
    notes: list[str] = Field(min_length=2, max_length=3, description="2-3 concrete, kind coaching notes.")


def coaching_notes(
    question: str,
    transcript: str,
    metrics: NonVerbalMetrics,
    samples: list[NonVerbalSample],
) -> list[str]:
    """2-3 kind, concrete notes from the LLM; falls back to rule-based notes if the LLM is unavailable."""
    duration = (samples[-1].t + 1) if samples else 0
    spans = look_away_spans(samples)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        question=question,
        transcript=transcript or "(no transcript)",
        duration_s=duration,
        metrics=metrics.model_dump_json(indent=2),
        look_away_spans=", ".join(f"{a}-{b} s" for a, b in spans) or "none",
    )
    try:
        return complete_json(prompt, CoachingNotes, temperature=0.3).notes
    except Exception:  # LLMError, or a missing provider package / API key
        return fallback_notes(metrics, samples)


def fallback_notes(metrics: NonVerbalMetrics, samples: list[NonVerbalSample]) -> list[str]:
    """Deterministic notes for offline demos; ordered by score weight."""
    notes: list[str] = []
    if metrics.eye_contact_pct < 70:
        spans = look_away_spans(samples)
        where = f", mostly around {spans[0][0]}-{spans[0][1]} s" if spans else ""
        notes.append(
            f"Your head or eyes were off the screen for {100 - metrics.eye_contact_pct:.0f}% of the answer{where}. "
            "When you need to think, pause and keep your eyes on the screen instead of looking down."
        )
    if "slouching" in metrics.posture_flags:
        notes.append("You sank lower in your seat as the answer went on. Sit back with both feet flat so you stay upright.")
    if "leaning_out_of_frame" in metrics.posture_flags:
        notes.append("You drifted towards the edge of the frame. Centre yourself so the interviewer can see you the whole time.")
    if "shoulders_tilted" in metrics.posture_flags:
        notes.append("Your shoulders were tilted for much of the answer. Square them to the camera; it reads as more confident.")
    habits = {a: pct for a, pct in metrics.hand_actions.items() if a in DISTRACTING_ACTIONS}
    if habits and metrics.fidget_pct >= 15:
        worst = max(habits, key=habits.get)
        tip = {
            "covering_mouth": "Keep your hands below your chin so your voice and expression come through clearly.",
            "touching_face": "Rest your hands on the desk; touching your face can read as nervousness.",
            "touching_head": "Rest your hands on the desk; playing with your hair can read as nervousness.",
            "fiddling": "Rest your hands lightly together, or hold a pen still, to stop the fiddling.",
            "restless": "Rest your hands on the desk and save movement for one gesture on your key point.",
            "fist": "Relax your hands open on the desk; clenched fists look tense.",
        }[worst]
        notes.append(f"You were {HAND_ACTION_TEXT[worst]} for {habits[worst]:.0f}% of the answer. {tip}")
    if metrics.expression_label == "tense":
        notes.append(
            "Your face looked tense for a good part of the answer (lowered brows or pressed lips). "
            "Relax your jaw and smile briefly when you introduce the situation."
        )
    if len(notes) < 2:
        notes.append(
            "Your eye contact was steady. Keep it up through the Result part of your answer, where people most often look away."
            if metrics.eye_contact_pct >= 70
            else "Practise this answer once more while watching the eye-contact ring."
        )
    if len(notes) < 2 and metrics.hand_actions.get("gesturing", 0) >= 15:
        notes.append("Your open-hand gestures helped you come across as engaged. Keep using them on your key points.")
    if len(notes) < 2:
        notes.append("Your posture and hands stayed calm. Keep that steady presence in the real interview.")
    return notes[:3]


# --------------------------------------------------------------------------- helpers

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _variance(xs: list[float]) -> float:
    """Population variance; 0 for fewer than two values (same as the browser)."""
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return _mean([(x - m) ** 2 for x in xs])


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, v))


def _round(v: float, digits: int) -> float:
    """Round half up, like JavaScript's Math.round (Python's round() rounds half to even)."""
    f = 10**digits
    return math.floor(v * f + 0.5) / f
