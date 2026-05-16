"""SSE endpoint for live run events.

Two event categories:
- `event: run_state`  — lifecycle deltas (created, step_started, step_exited,
  running, completed, failed, cancelled, daemon_started, daemon_status,
  daemon_ended).
- `event: run_output` — incremental stdout/stderr per step. Payload obeys the
  step's `StreamConfig` (lines vs. binary).

Late subscribers should fetch `…/runs/{slug}/state` for a snapshot first,
then attach here for deltas. There is no in-band snapshot event.
"""

from __future__ import annotations

import asyncio
import json

import ihate_work.o11y as o11y
from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from xumret.protocol.service import XumretService
from xumret.server.api import get_service
from xumret.state.models import RunOutputEvent

logger, *_ = o11y.get_o11y(__name__)

router = APIRouter(prefix="/api")


@router.get("/events")
async def event_stream(
    request: Request,
    svc: XumretService = Depends(get_service),
) -> StreamingResponse:
    queue = svc.subscribe()

    logger.info("sse client connected")

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                category = (
                    "run_output" if isinstance(event, RunOutputEvent) else "run_state"
                )
                payload = json.dumps(event.model_dump(mode="json"))
                yield f"event: {category}\ndata: {payload}\n\n"
        finally:
            logger.info("sse client disconnected")
            svc.unsubscribe(queue)

    return StreamingResponse(generate(), media_type="text/event-stream")
