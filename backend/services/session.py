"""In-memory store of Profiles, one per browser session (no accounts, no database).

The frontend sends an `X-Session-Id` header it generated for the tab; backend/main.py puts that id in
`current` for the request, and every module reads and writes "the profile" through these functions
without knowing about sessions. Requests without the header (tests, scripts) share the "default" slot.
"Delete my data" calls reset_profile().
"""
from __future__ import annotations

import re
import threading
from contextvars import ContextVar

from backend.schemas import Profile

DEFAULT_SESSION = "default"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

current: ContextVar[str] = ContextVar("careerlens_session", default=DEFAULT_SESSION)

_lock = threading.Lock()
_profiles: dict[str, Profile] = {}


def session_id_from_header(value: str | None) -> str:
    """The session to use for a request: the header when it is a safe token, else the default slot."""
    return value if value and _SAFE_ID.match(value) else DEFAULT_SESSION


def current_session() -> str:
    return current.get()


def get_profile() -> Profile:
    with _lock:
        return _profiles.get(current.get(), _EMPTY).model_copy(deep=True)


def set_profile(profile: Profile) -> None:
    with _lock:
        _profiles[current.get()] = profile.model_copy(deep=True)


def update_profile(**fields) -> Profile:
    """Replace the given top-level fields and return the updated profile."""
    with _lock:
        key = current.get()
        updated = _profiles.get(key, _EMPTY).model_copy(update=fields)
        _profiles[key] = updated
        return updated.model_copy(deep=True)


def reset_profile() -> None:
    with _lock:
        _profiles.pop(current.get(), None)


def session_count() -> int:
    with _lock:
        return len(_profiles)


_EMPTY = Profile()
