"""One place that turns service errors into HTTP errors, so every router answers the same way."""
from __future__ import annotations

import math

from fastapi import HTTPException

from backend.llm_adapter import LLMError
from backend.services.data import DataError, JobNotFound, RoleNotFound

HANDLED = (RoleNotFound, JobNotFound, DataError, LLMError)


def http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (RoleNotFound, JobNotFound)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, DataError):
        return HTTPException(status_code=503, detail=f"Data not ready: {exc}")
    if isinstance(exc, LLMError):
        # The raw provider text stays in the server log; the UI gets a short, safe sentence.
        headers = {"Retry-After": str(math.ceil(exc.retry_after_s))} if exc.retry_after_s else None
        return HTTPException(status_code=exc.http_status, detail=exc.user_message, headers=headers)
    raise exc
