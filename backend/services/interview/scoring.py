"""Verbal score, readiness fusion and "what to fix" feedback. Owner: M3.

    verbal     = 0.40*STAR + 0.20*conciseness + 0.15*fillers + 0.15*relevance + 0.10*pace
    non_verbal = mean body-language score over the answers with video (services/interview/nonverbal.py)
    readiness  = 0.70*verbal + 0.30*non_verbal     (= verbal when there was no video)

Every component is 0-100. For a typed answer there is no pace, so the other weights are scaled up.
Relevance is the embedding cosine between question and answer (same embedding model as the skill
matcher). Without the model it is left out and the other weights are scaled up, rather than guessed.
"""
from __future__ import annotations

import logging

from backend.llm_adapter import embed
from backend.schemas.interview import AnswerResult, InterviewReport, NonVerbalMetrics, StarScore, VerbalMetrics
from backend.services.interview import fillers, pace
from backend.services.interview.nonverbal import DISTRACTING_ACTIONS, HAND_ACTION_TEXT, session_non_verbal_score
from backend.services.interview.star import ELEMENTS, star_score

log = logging.getLogger(__name__)

VERBAL_WEIGHTS = {"star": 0.40, "conciseness": 0.20, "fillers": 0.15, "relevance": 0.15, "pace": 0.10}
VERBAL_WEIGHT = 0.70
NON_VERBAL_WEIGHT = 0.30

# Cosine of an on-topic answer vs the question is ~0.5+ with MiniLM; off-topic ~0.1.
RELEVANCE_ZERO = 0.15
RELEVANCE_FULL = 0.55

# --------------------------------------------------------------------------- per answer

def verbal_metrics(question: str, transcript: str, duration_s: float, star: StarScore, kind: str = "behavioural") -> VerbalMetrics:
    words = fillers.word_count(transcript)
    counts = fillers.count_fillers(transcript)
    per_100 = fillers.fillers_per_100_words(counts, words)
    rate = pace.wpm(words, duration_s)
    concise_score, concise = pace.conciseness(words, duration_s, kind)
    cos = relevance_cosine(question, transcript)

    components = {
        "star": star_score(star),
        "conciseness": concise_score,
        "fillers": fillers.filler_score(per_100),
    }
    if cos is not None:
        components["relevance"] = relevance_score(cos)
    if duration_s > 0:
        components["pace"] = pace.pace_score(rate)
    return VerbalMetrics(
        word_count=words,
        duration_s=round(max(0.0, duration_s), 1),
        wpm=rate,
        pace_band=pace.pace_band(rate, duration_s),
        filler_counts=counts,
        fillers_per_100_words=per_100,
        star=star,
        relevance=None if cos is None else round(max(0.0, min(1.0, cos)), 3),
        concise=concise,
        component_scores=components,
    )


def verbal_score(components: dict[str, float]) -> float:
    """Weighted mean of the components present (no pace for typed answers, no relevance without embeddings)."""
    used = {k: w for k, w in VERBAL_WEIGHTS.items() if k in components}
    total = sum(used.values())
    if not total:
        return 0.0
    return round(sum(components[k] * w for k, w in used.items()) / total, 1)


def readiness(verbal: float, non_verbal: float | None) -> float:
    if non_verbal is None:
        return round(verbal, 1)
    return round(VERBAL_WEIGHT * verbal + NON_VERBAL_WEIGHT * non_verbal, 1)


def relevance_cosine(question: str, answer: str) -> float | None:
    """Cosine between question and answer embeddings; None when no embedding model is available."""
    if not answer.strip():
        return 0.0
    try:
        q, a = embed([question, answer])
    except Exception as exc:  # sentence-transformers not installed, no key, no network
        log.info("Embedding unavailable, relevance left out of the score: %s", exc)
        return None
    return sum(x * y for x, y in zip(q, a))


def relevance_score(cos: float) -> float:
    return round(100 * max(0.0, min(1.0, (cos - RELEVANCE_ZERO) / (RELEVANCE_FULL - RELEVANCE_ZERO))), 1)


def content_feedback(v: VerbalMetrics) -> list[str]:
    """What to fix in the answer itself, most important first (at most 4 items)."""
    notes: list[str] = []
    missing = [n for n in ELEMENTS if not getattr(v.star, n).present]
    if "result" in missing:
        notes.append("You never said how it ended. Finish with the Result: what changed, ideally with a number (time saved, accuracy, grade).")
    other_missing = [n.title() for n in missing if n != "result"]
    if other_missing:
        notes.append(f"Your answer had no clear {' or '.join(other_missing)}. Use the STAR order so the interviewer can follow the story.")
    weak = [n.title() for n in ELEMENTS if getattr(v.star, n).present and getattr(v.star, n).strength == 1]
    if weak:
        notes.append(f"Your {', '.join(weak)} {'was' if len(weak) == 1 else 'were'} vague. Add specifics: names of tools, numbers, what exactly you did.")
    if v.fillers_per_100_words > fillers.FREE_PER_100 and v.filler_counts:
        top = max(v.filler_counts, key=v.filler_counts.get)
        notes.append(
            f'You used {sum(v.filler_counts.values())} filler words ({v.fillers_per_100_words} per 100 words), mostly "{top}". '
            "Pause silently instead."
        )
    if v.component_scores.get("conciseness", 100) < 80:
        low = v.word_count < pace.WORD_BANDS["behavioural"][0]
        notes.append(
            "The answer was short. Aim for 90 seconds to 3 minutes so you have room for the Action and Result."
            if low
            else "The answer ran long. Keep to about 2 minutes: one sentence of Situation, then go straight to what you did."
        )
    if v.pace_band == "fast":
        notes.append(f"You spoke quickly ({v.wpm:.0f} words per minute). Slow down to 120-160 and pause between the STAR parts.")
    elif v.pace_band == "slow":
        notes.append(f"You spoke slowly ({v.wpm:.0f} words per minute). Practise the story so it flows at 120-160 words per minute.")
    if v.component_scores.get("relevance", 100) < 50:
        notes.append("The answer drifted from the question. Repeat the question's key words in your first sentence and stay on that one example.")
    return notes[:4]


# --------------------------------------------------------------------------- whole interview

def build_report(role: str, answers: list[AnswerResult]) -> InterviewReport:
    verbal = round(sum(a.verbal_score for a in answers) / len(answers), 1) if answers else 0.0
    non_verbal = session_non_verbal_score([a.non_verbal for a in answers])
    return InterviewReport(
        role=role,
        answers=answers,
        verbal_score=verbal,
        non_verbal_score=non_verbal,
        readiness=readiness(verbal, non_verbal),
        verbal_weight=VERBAL_WEIGHT,
        non_verbal_weight=NON_VERBAL_WEIGHT,
        fix_first=fix_first(answers),
    )


def fix_first(answers: list[AnswerResult]) -> str:
    """The single change worth the most readiness points, from the averages over all answers."""
    if not answers:
        return ""
    has_video = any(a.non_verbal for a in answers)
    vw = VERBAL_WEIGHT if has_video else 1.0
    losses: list[tuple[float, str]] = []

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 100.0

    for comp, w in VERBAL_WEIGHTS.items():
        values = [a.verbal.component_scores[comp] for a in answers if comp in a.verbal.component_scores]
        losses.append((vw * w * (100 - avg(values)), _VERBAL_FIX[comp](answers)))

    videos = [a.non_verbal for a in answers if a.non_verbal]
    if videos:
        nw = NON_VERBAL_WEIGHT
        losses.append((nw * 0.35 * (100 - avg([m.eye_contact_pct for m in videos])), "Keep your head and eyes on the screen, especially while you think: pause instead of looking away."))
        losses.append((nw * 0.20 * avg([m.fidget_pct for m in videos]), _hand_fix(videos)))
        tense = sum(m.expression_label == "tense" for m in videos) / len(videos)
        losses.append((nw * 0.10 * 70 * tense, "Relax your face: unclench your jaw and smile briefly when you set the scene."))
        slouch = sum(bool(m.posture_flags) for m in videos) / len(videos)
        losses.append((nw * 0.25 * 60 * slouch, "Sit upright and centred in the frame for the whole answer."))

    loss, message = max(losses, key=lambda x: x[0])
    return message if loss > 2 else "Strong interview. Keep practising with new questions to stay consistent."


def _hand_fix(videos: list[NonVerbalMetrics]) -> str:
    totals: dict[str, float] = {}
    for m in videos:
        for action, pct in m.hand_actions.items():
            if action in DISTRACTING_ACTIONS:
                totals[action] = totals.get(action, 0) + pct
    if not totals:
        return "Keep your hands calm and use open-hand gestures on your key points."
    worst = max(totals, key=totals.get)
    return f"Stop {HAND_ACTION_TEXT[worst]}: rest your hands on the desk and use one open gesture for your key point."


def _missing_result(answers: list[AnswerResult]) -> str:
    missing = [n for n in ELEMENTS if sum(not getattr(a.verbal.star, n).present for a in answers) * 2 >= len(answers)]
    if "result" in missing:
        return "End every answer with a Result: what changed, with a number if you can (time saved, accuracy, grade)."
    if missing:
        return f"Structure every answer as STAR - you often skipped the {missing[0].title()}."
    return "Make each STAR part specific: name your tools and give at least one number."


_VERBAL_FIX = {
    "star": _missing_result,
    "conciseness": lambda a: "Aim for answers of about 2 minutes: one sentence of context, most of the time on what you did and the result.",
    "fillers": lambda a: "Cut the filler words: when you need a moment, pause silently instead of saying 'um' or 'like'.",
    "relevance": lambda a: "Answer the exact question: repeat its key words in your first sentence and stick to one example.",
    "pace": lambda a: "Speak at 120-160 words per minute, with a short pause between the STAR parts.",
}
