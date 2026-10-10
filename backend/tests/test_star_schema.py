"""STAR scoring: the LLM's quotes must really be in the transcript, and the offline fallback must work."""
import pytest

from backend.llm_adapter import LLMError
from backend.schemas.interview import StarElement
from backend.services.interview import star

TRANSCRIPT = (
    "Last year during my internship at a logistics startup, the weekly sales report took two days to build by hand. "
    "My task was to automate it. I wrote a Python script with pandas that pulled the data from SQL. "
    "As a result, the report took 10 minutes instead of two days."
)


def _llm_reply(**elements):
    def fake(prompt, schema, **_kwargs):
        assert TRANSCRIPT in prompt
        base = {n: StarElement(present=False) for n in star.ELEMENTS}
        return schema(**(base | elements))

    return fake


def test_keeps_quotes_that_are_in_the_transcript(monkeypatch):
    monkeypatch.setattr(star, "complete_json", _llm_reply(
        situation=StarElement(present=True, evidence_span="the weekly sales report took two days to build by hand", strength=2),
        action=StarElement(present=True, evidence_span="I wrote a Python script with pandas", strength=3),
    ))
    s = star.analyze_star("Tell me about automating something.", TRANSCRIPT)
    assert s.source == "llm"
    assert s.situation.present and s.situation.strength == 2
    assert s.action.evidence_span == "I wrote a Python script with pandas"
    assert not s.result.present


def test_drops_a_hallucinated_result(monkeypatch):
    monkeypatch.setattr(star, "complete_json", _llm_reply(
        result=StarElement(present=True, evidence_span="my manager promoted me to team lead", strength=3),
    ))
    s = star.analyze_star("Q?", TRANSCRIPT)
    assert s.result == StarElement(present=False, evidence_span="", strength=0)


def test_empty_quote_means_absent(monkeypatch):
    monkeypatch.setattr(star, "complete_json", _llm_reply(task=StarElement(present=True, evidence_span="", strength=2)))
    assert not star.analyze_star("Q?", TRANSCRIPT).task.present


def test_snaps_near_verbatim_quotes_to_the_transcript():
    # Different case, missing comma, curly quotes: still the same words.
    found = star.find_span("“as a result the report took 10 minutes”", TRANSCRIPT)
    assert found == "As a result, the report took 10 minutes"
    assert star.find_span("we hired three more analysts", TRANSCRIPT) is None


def test_falls_back_to_cue_phrases_without_an_llm(monkeypatch):
    def boom(*_a, **_k):
        raise LLMError("no key")

    monkeypatch.setattr(star, "complete_json", boom)
    s = star.analyze_star("Q?", TRANSCRIPT)
    assert s.source == "rules"
    assert all(getattr(s, n).present for n in star.ELEMENTS)
    assert s.result.strength == 3  # has a number
    assert s.task.strength == 1  # short and vague
    assert star.star_score(s) == pytest.approx(100 * (2 + 1 + 2 + 3) / 12, abs=0.1)


def test_rules_find_nothing_in_an_off_topic_answer():
    s = star.rule_based_star("I like data. Data is important for companies.")
    assert star.star_score(s) == 0


def test_empty_transcript():
    assert star.star_score(star.analyze_star("Q?", "   ")) == 0
