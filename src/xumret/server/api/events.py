"""SSE endpoint for real-time command updates."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from xumret.state.manager import StateManager

router = APIRouter(prefix="/api")

_state: StateManager | None = None


def init(state_manager: StateManager) -> None:
    global _state
    _state = state_manager


def _sm() -> StateManager:
    assert _state is not None, "events not initialised"
    return _state


@router.get("/events")
async def event_stream(request: Request) -> StreamingResponse:
    queue = _sm().subscribe()

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        finally:
            _sm().unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")
