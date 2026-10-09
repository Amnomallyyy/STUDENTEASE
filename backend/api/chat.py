"""Chat route: server-sent events. Register with app.include_router(chat.router)."""
from __future__ import annotations

import json
from typing import Any, Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.schemas import ChatRequest
from backend.services import session
from backend.services.chat import stream_reply

router = APIRouter(tags=["chat"])


def _sse(events: Iterator[dict[str, Any]]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(event)}\n\n"


@router.post("/chat")
def post_chat(request: ChatRequest) -> StreamingResponse:
    events = stream_reply(request.message, request.history, session.get_profile())
    return StreamingResponse(_sse(events), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
