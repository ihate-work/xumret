"""SSE endpoint for real-time command updates."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from xumret.protocol.service import XumretService

router = APIRouter(prefix="/api")


def get_service(request: Request) -> XumretService:
    return request.app.state.service


@router.get("/events")
async def event_stream(
    request: Request,
    svc: XumretService = Depends(get_service),
) -> StreamingResponse:
    queue = svc.subscribe()

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: {event.type}\ndata: {json.dumps(event.data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            svc.unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")
