"""REST endpoints for run management.

Verbs: GET (safe), POST (named idempotent action). DELETE not used.
See `doc/design-process-management.md` for semantics.
"""

from __future__ import annotations

import ihate_work.o11y as o11y
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from xumret.executor.models import PhoneCommand
from xumret.protocol.service import XumretService
from xumret.server.api import get_service
from xumret.state.models import RunRecord
from xumret.state.phone import StillLive, SubmitConflict

logger, *_ = o11y.get_o11y(__name__)

router = APIRouter(prefix="/api")


class SubmitRequest(BaseModel):
    phone_command: PhoneCommand


# --- submit / list ---


@router.post("/runs")
async def submit_run(
    req: SubmitRequest,
    svc: XumretService = Depends(get_service),
) -> RunRecord:
    pc = req.phone_command
    logger.info(
        "submit",
        name=pc.name,
        daemon=pc.daemon,
        slug=pc.run_option.slug,
        mutex_by_slug=pc.run_option.mutex_by_slug,
    )
    try:
        return await svc.submit(pc)
    except SubmitConflict as e:
        raise HTTPException(status_code=409, detail={
            "slug": e.slug, "reason": e.reason,
        }) from e


@router.get("/runs")
async def list_runs(
    svc: XumretService = Depends(get_service),
) -> list[RunRecord]:
    return await svc.list()


# --- per-run ---


@router.get("/runs/{slug}")
async def get_run(
    slug: str,
    svc: XumretService = Depends(get_service),
) -> RunRecord:
    record = await svc.get(slug)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@router.get("/runs/{slug}/state")
async def get_run_state(
    slug: str,
    svc: XumretService = Depends(get_service),
) -> RunRecord:
    record = await svc.get_state(slug)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@router.post("/runs/{slug}/stop")
async def stop_run(
    slug: str,
    svc: XumretService = Depends(get_service),
) -> RunRecord:
    logger.info("stop", slug=slug)
    record = await svc.stop(slug)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@router.post("/runs/{slug}/reap")
async def reap_run(
    slug: str,
    svc: XumretService = Depends(get_service),
) -> dict:
    logger.info("reap", slug=slug)
    try:
        ok = await svc.reap(slug)
    except StillLive as e:
        raise HTTPException(status_code=409, detail={
            "slug": e.slug, "reason": "still-live",
        }) from e
    if not ok:
        raise HTTPException(status_code=404, detail="run not found")
    return {"slug": slug, "reaped": True}
