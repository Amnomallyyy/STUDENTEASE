"""Speaking pace and answer length. Pure code, no LLM. Owner: M3.

Bands (outline section 3): behavioural answers 90-180 s and 150-300 words; pace 120-160 words per
minute. Scores are 100 inside a band and fall off linearly outside it.
"""
from __future__ import annotations

from typing import Literal

WPM_BAND = (120.0, 160.0)
WPM_ZERO = (60.0, 220.0)  # pace scores 0 at or beyond these
WORD_BANDS = {"behavioural": (150, 300), "situational": (120, 250), "technical": (80, 250)}
DURATION_BANDS = {"behavioural": (90.0, 180.0), "situational": (75.0, 160.0), "technical": (45.0, 150.0)}


def wpm(words: int, duration_s: float) -> float:
    return round(words / duration_s * 60, 1) if duration_s > 0 else 0.0


def pace_band(rate: float, duration_s: float) -> Literal["slow", "within", "fast", "unknown"]:
    if duration_s <= 0:
        return "unknown"
    if rate < WPM_BAND[0]:
        return "slow"
    if rate > WPM_BAND[1]:
        return "fast"
    return "within"


def pace_score(rate: float) -> float:
    lo, hi = WPM_BAND
    zlo, zhi = WPM_ZERO
    if lo <= rate <= hi:
        return 100.0
    if rate < lo:
        return round(max(0.0, 100 * (rate - zlo) / (lo - zlo)), 1)
    return round(max(0.0, 100 * (zhi - rate) / (zhi - hi)), 1)


def _band_score(value: float, lo: float, hi: float) -> float:
    """100 inside [lo, hi]; proportional below (half the band = 50); loses 1 point per 1% over."""
    if lo <= value <= hi:
        return 100.0
    if value < lo:
        return round(100 * value / lo, 1)
    return round(max(0.0, 100 - 100 * (value - hi) / hi), 1)


def conciseness(words: int, duration_s: float, kind: str = "behavioural") -> tuple[float, bool]:
    """(0-100 score, within the word band). Duration counts too when the answer was spoken."""
    wlo, whi = WORD_BANDS.get(kind, WORD_BANDS["behavioural"])
    score = _band_score(words, wlo, whi)
    if duration_s > 0:
        dlo, dhi = DURATION_BANDS.get(kind, DURATION_BANDS["behavioural"])
        score = min(score, _band_score(duration_s, dlo, dhi))
    return score, wlo <= words <= whi
