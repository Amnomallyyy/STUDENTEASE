"""Mock interview routes (M3). backend/main.py registers this router when the module exists.

    POST /interview/start   {role?, count?}                          -> list[InterviewQuestion]
    POST /interview/answer  multipart: question_id, transcript, duration_s, samples (JSON), audio? -> AnswerResult
    GET  /interview/report                                           -> InterviewReport
    POST /interview/transcribe  multipart: audio (a few seconds)     -> {text}   (live filler counting)

Video never reaches the server: `samples` is the browser's 1 Hz list of NonVerbalSample numbers.
The latest report is also written to the shared profile so the chatbot can explain the score.
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from backend.schemas.interview import AnswerResult, InterviewQuestion, InterviewReport, NonVerbalSample
from backend.services import session
from backend.services.interview import nonverbal, scoring
from backend.services.interview.questions import generate_questions
from backend.services.interview.rewrite import rewrite_answer
from backend.services.interview.star import analyze_star
from backend.services.interview.transcribe import transcribe

router = APIRouter(prefix="/interview", tags=["interview"])

MAX_AUDIO_BYTES = 15 * 1024 * 1024
_samples_adapter = TypeAdapter(list[NonVerbalSample])


class StartRequest(BaseModel):
    role: str | None = Field(default=None, description="Defaults to the profile's target role.")
    count: int = Field(default=3, ge=1, le=5)


class _Interview:
    """The one in-memory interview (no accounts: one session, like the profile)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.role = ""
        self.questions: dict[str, InterviewQuestion] = {}
        self.answers: dict[str, AnswerResult] = {}

    def ordered_answers(self) -> list[AnswerResult]:
        return [self.answers[q] for q in self.questions if q in self.answers]


_state = _Interview()


@router.post("/start", response_model=list[InterviewQuestion])
def start(body: StartRequest) -> list[InterviewQuestion]:
    profile = session.get_profile()
    role = (body.role or profile.target_role or "").strip()
    if not role:
        raise HTTPException(status_code=422, detail="Pick a target role first.")
    questions = generate_questions(role, profile, body.count)
    with _state.lock:
        _state.role = role
        _state.questions = {q.id: q for q in questions}
        _state.answers = {}
    return questions


@router.post("/answer", response_model=AnswerResult)
def answer(
    question_id: str = Form(...),
    transcript: str = Form(default=""),
    duration_s: float = Form(default=0.0, ge=0, description="0 for a typed answer."),
    samples: str = Form(default="[]", description="JSON list of NonVerbalSample from the browser; [] = camera off."),
    audio: UploadFile | None = File(default=None),
) -> AnswerResult:
    with _state.lock:
        question = _state.questions.get(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Unknown question. Start a new interview.")
    try:
        nv_samples = _samples_adapter.validate_python(json.loads(samples or "[]"))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid body-language samples: {exc}") from exc

    if audio is not None:
        content = audio.file.read(MAX_AUDIO_BYTES + 1)
        if len(content) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio is larger than 15 MB.")
        transcript = transcribe(content, audio.filename or "answer.webm") or transcript
    transcript = transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="No answer was heard. Try again, or type your answer.")

    result = analyze_answer(question, transcript, duration_s, nv_samples)
    with _state.lock:
        _state.answers[question_id] = result
        report = scoring.build_report(_state.role, _state.ordered_answers())
    session.update_profile(interview=report)
    return result


class TranscribeResponse(BaseModel):
    text: str | None = Field(description="None when no Whisper provider is configured or the clip had no speech.")


MAX_CLIP_BYTES = 2 * 1024 * 1024


@router.post("/transcribe", response_model=TranscribeResponse)
def transcribe_clip(audio: UploadFile = File(...)) -> TranscribeResponse:
    """Transcribe a short clip while the user is still speaking. The browser's own speech recognition
    drops "um" and "uh", so the live filler gauge counts from these Whisper clips instead."""
    content = audio.file.read(MAX_CLIP_BYTES + 1)
    if len(content) > MAX_CLIP_BYTES:
        raise HTTPException(status_code=413, detail="Clip is larger than 2 MB; send a few seconds at a time.")
    return TranscribeResponse(text=transcribe(content, audio.filename or "clip.webm"))


@router.get("/report", response_model=InterviewReport)
def report() -> InterviewReport:
    with _state.lock:
        if not _state.questions:
            raise HTTPException(status_code=404, detail="No interview yet. Start one first.")
        return scoring.build_report(_state.role, _state.ordered_answers())


def analyze_answer(
    question: InterviewQuestion, transcript: str, duration_s: float, samples: list[NonVerbalSample]
) -> AnswerResult:
    """Score one answer. STAR first (the rewrite needs it), then rewrite and coaching notes in parallel."""
    star = analyze_star(question.text, transcript)
    verbal = scoring.verbal_metrics(question.text, transcript, duration_s, star, question.kind)
    non_verbal = nonverbal.analyze_answer(samples)
    with ThreadPoolExecutor(max_workers=2) as pool:
        rewrite = pool.submit(rewrite_answer, question.text, transcript, star)
        notes = pool.submit(nonverbal.coaching_notes, question.text, transcript, non_verbal, samples) if non_verbal else None
        rewritten = rewrite.result()
        coaching = notes.result() if notes else []
    return AnswerResult(
        question=question,
        transcript=transcript,
        verbal=verbal,
        non_verbal=non_verbal,
        verbal_score=scoring.verbal_score(verbal.component_scores),
        rewritten_answer=rewritten,
        coaching_notes=coaching,
        content_feedback=scoring.content_feedback(verbal),
    )
