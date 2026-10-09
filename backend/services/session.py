"""In-memory store for the one shared Profile (no accounts: one session, one profile).

Other modules (M3 interview, M5 analyzer) read and write the profile through these functions.
"Delete my data" calls reset_profile().
"""
from __future__ import annotations

import threading

from backend.schemas import Profile

_lock = threading.Lock()
_profile = Profile()


def get_profile() -> Profile:
    with _lock:
        return _profile.model_copy(deep=True)


def set_profile(profile: Profile) -> None:
    global _profile
    with _lock:
        _profile = profile.model_copy(deep=True)


def update_profile(**fields) -> Profile:
    """Replace the given top-level fields and return the updated profile."""
    global _profile
    with _lock:
        _profile = _profile.model_copy(update=fields)
        return _profile.model_copy(deep=True)


def reset_profile() -> None:
    set_profile(Profile())
