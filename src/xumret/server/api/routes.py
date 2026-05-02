"""REST endpoints for command management."""

from __future__ import annotations

from typing import Any

import ihate_work.o11y as o11y
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from xumret.executor.models import PhoneCommand
from xumret.protocol.service import XumretService
from xumret.server.api import get_service
from xumret.state.models import CommandHandle, CommandRecord

logger, *_ = o11y.get_o11y(__name__)

router = APIRouter(prefix="/api")


class SubmitRequest(BaseModel):
    phone_command: PhoneCommand


class CommandResponse(BaseModel):
    command_id: str
    status: str
    result: dict[str, Any] | None = None
    daemon_handle: dict[str, Any] | None = None
    error: str | None = None
    created_at: float
    updated_at: float


def _to_response(record: CommandRecord) -> CommandResponse:
    return CommandResponse(
        command_id=record.command_id,
        status=record.status.value,
        result=record.result.model_dump() if record.result else None,
        daemon_handle=record.daemon_handle.model_dump() if record.daemon_handle else None,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/commands")
async def submit_command(
    req: SubmitRequest,
    svc: XumretService = Depends(get_service),
) -> CommandHandle:
    logger.info("submit", command_name=req.phone_command.name, daemon=req.phone_command.daemon)
    return await svc.submit(req.phone_command)


@router.get("/commands")
async def list_commands(
    svc: XumretService = Depends(get_service),
) -> list[CommandResponse]:
    records = await svc.list()
    return [_to_response(r) for r in records]


@router.get("/commands/{command_id}")
async def get_command(
    command_id: str,
    svc: XumretService = Depends(get_service),
) -> CommandResponse:
    record = await svc.get(command_id)
    if not record:
        raise HTTPException(status_code=404, detail="command not found")
    return _to_response(record)


@router.delete("/commands/{command_id}")
async def cancel_command(
    command_id: str,
    svc: XumretService = Depends(get_service),
) -> CommandResponse:
    logger.info("cancel", command_id=command_id)
    record = await svc.cancel(command_id)
    if not record:
        raise HTTPException(status_code=404, detail="command not found")
    return _to_response(record)
