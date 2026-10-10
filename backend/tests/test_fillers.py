import pytest

from backend.services.interview import fillers, pace


def test_counts_always_fillers_and_phrases():
    counts = fillers.count_fillers("Um, I mean, it was basically, uh, kind of broken. You know? Actually it was.")
    assert counts == {"um": 1, "i mean": 1, "basically": 1, "uh": 1, "kind of": 1, "you know": 1, "actually": 1}


def test_like_only_counts_as_a_filler():
    text = "I would like to say it looks like SQL. It was like, slow. And like we fixed it."
    assert fillers.count_fillers(text)["like"] == 2


def test_so_only_counts_at_the_start_of_a_clause():
    text = "So, I built it so that it ran. It was so much faster. Then, so we shipped it."
    assert fillers.count_fillers(text)["so"] == 2


def test_clean_answer_has_no_fillers():
    assert fillers.count_fillers("I designed the schema and wrote the queries myself.") == {}


def test_rate_and_score():
    assert fillers.word_count("It's a 2-day job, isn't it?") == 7
    assert fillers.fillers_per_100_words({"um": 3}, 50) == 6.0
    assert fillers.filler_score(2.0) == 100.0  # normal speech is free
    assert fillers.filler_score(7.0) == 50.0
    assert fillers.filler_score(15.0) == 0.0


@pytest.mark.parametrize(
    ("rate", "band", "score"),
    [(140, "within", 100.0), (90, "slow", 50.0), (190, "fast", 50.0), (40, "slow", 0.0)],
)
def test_pace(rate, band, score):
    assert pace.pace_band(rate, 60) == band
    assert pace.pace_score(rate) == score


def test_typed_answer_has_unknown_pace():
    assert pace.wpm(100, 0) == 0.0
    assert pace.pace_band(0, 0) == "unknown"


def test_conciseness_bands():
    assert pace.conciseness(200, 120) == (100.0, True)
    assert pace.conciseness(75, 0) == (50.0, False)  # half the minimum words, typed
    assert pace.conciseness(200, 45)[0] == 50.0  # right length but rushed: duration counts too
    assert pace.conciseness(450, 0)[0] == 50.0  # 50% over the maximum
