import json
from pathlib import Path

import pytest

from backend.llm_adapter import LLMError
from backend.schemas.interview import NonVerbalMetrics, NonVerbalSample
from backend.services.interview import nonverbal

FIXTURES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "vision" / "__fixtures__" / "answers.json"
CASES = {k: v for k, v in json.loads(FIXTURES.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def samples(case: str) -> list[NonVerbalSample]:
    return [NonVerbalSample(**s) for s in CASES[case]["samples"]]


@pytest.mark.parametrize("case", sorted(CASES))
def test_matches_shared_fixture(case):
    """Same expected values as frontend/src/vision/__tests__/metrics.test.ts."""
    metrics, subs = nonverbal.analyze_answer_detailed(samples(case))
    expected = CASES[case]["expected"]
    assert metrics.model_dump() == expected["metrics"]
    for key, value in expected["sub_scores"].items():
        assert getattr(subs, key) == pytest.approx(value)


def test_mixed_answer_by_hand():
    m = nonverbal.analyze_answer(samples("mixed"))
    assert m.eye_contact_pct == 69.2  # (8 full seconds + 0.1 + 0 + 0.2) / 12; seconds 4-5 are eyes-only look-aways
    assert m.fidget_pct == 25.0  # touching face + fiddling + restless = 3 of 12 seconds
    assert m.hand_actions["gesturing"] == 16.7  # gestures are reported but not penalised
    assert m.nod_count == 1


def test_verbal_only_mode():
    assert nonverbal.analyze_answer([]) is None
    assert nonverbal.session_non_verbal_score([None, None]) is None


def test_old_payload_without_m4_fields_still_scores():
    s = NonVerbalSample(
        t=0, head_yaw_deg=30, head_pitch_deg=0, nose_x=0.5, nose_y=0.5, shoulder_tilt_deg=0,
        forward_lean=0.9, wrist_velocity=0, smile=0, brow=0,
    )
    assert nonverbal.eye_contact_frac(s) == 0.0  # falls back to the averaged angles


def test_session_score_is_mean_of_answers_with_video():
    a = nonverbal.analyze_answer(samples("calm"))
    b = nonverbal.analyze_answer(samples("mixed"))
    assert nonverbal.session_non_verbal_score([a, None, b]) == pytest.approx((100.0 + 66.8) / 2, abs=0.05)


def test_look_away_spans():
    assert nonverbal.look_away_spans(samples("mixed")) == [(3, 5)]


def test_round_half_up_like_javascript():
    assert nonverbal._round(0.25, 1) == 0.3  # Python's round() would give 0.2


def test_coaching_notes_fall_back_without_llm(monkeypatch):
    def boom(*_args, **_kwargs):
        raise LLMError("no key")

    monkeypatch.setattr(nonverbal, "complete_json", boom)
    s = samples("mixed")
    notes = nonverbal.coaching_notes("Tell me about a time...", "So, um, I fixed it.", nonverbal.analyze_answer(s), s)
    assert 2 <= len(notes) <= 3
    assert "3-5 s" in notes[0]


def test_coaching_prompt_is_filled(monkeypatch):
    seen = {}

    def fake(prompt, schema, **_kwargs):
        seen["prompt"] = prompt
        return schema(notes=["one", "two"])

    monkeypatch.setattr(nonverbal, "complete_json", fake)
    s = samples("mixed")
    assert nonverbal.coaching_notes("Q?", "answer text", nonverbal.analyze_answer(s), s) == ["one", "two"]
    assert "3-5 s" in seen["prompt"] and "answer text" in seen["prompt"] and "{" in seen["prompt"]


def test_fallback_notes_for_good_answer():
    m = NonVerbalMetrics(
        eye_contact_pct=95, head_stability=0, posture_flags=[], fidget_pct=0,
        expression_label="engaged", nod_count=2, body_language_score=98,
    )
    assert len(nonverbal.fallback_notes(m, [])) == 2


def test_tense_face_is_detected():
    m = nonverbal.analyze_answer(samples("tense"))
    assert m.expression_label == "tense"  # 4 of 8 seconds with pressed lips / lowered brows
    assert m.hand_actions["fist"] == 25.0
    assert nonverbal.analyze_answer(samples("calm")).expression_label == "engaged"


def test_expression_falls_back_to_brow_for_old_payloads():
    base = CASES["calm"]["samples"][0] | {"smile": 0.0, "tension": None, "brow": 0.4}
    assert nonverbal.expression_label([NonVerbalSample(**base)]) == "tense"


def test_sitting_low_in_frame_counts_as_slouching():
    s = samples("calm")[0].model_copy(update={"nose_y": 0.7})
    assert nonverbal.is_slouching(s, baseline_lean=0)


def test_fallback_notes_name_the_hand_habit():
    s = samples("tense")
    notes = nonverbal.fallback_notes(nonverbal.analyze_answer(s), s)
    assert any("clenching your fists" in n for n in notes)
    assert any("tense" in n for n in notes)
