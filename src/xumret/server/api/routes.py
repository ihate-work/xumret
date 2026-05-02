"""REST endpoints for command management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from xumret.executor.models import PhoneCommand
from xumret.state.manager import StateManager

router = APIRouter(prefix="/api")

# Injected by app factory
_state: StateManager | None = None


def init(state_manager: StateManager) -> None:
    global _state
    _state = state_manager


def _sm() -> StateManager:
    assert _state is not None, "routes not initialised"
    return _state


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


def _to_response(record: Any) -> CommandResponse:
    return CommandResponse(
        command_id=record.command_id,
        status=record.status,
        result=record.result.model_dump() if record.result else None,
        daemon_handle=record.daemon_handle.model_dump() if record.daemon_handle else None,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/commands")
async def submit_command(req: SubmitRequest) -> CommandResponse:
    record = await _sm().submit_command(req.phone_command)
    return _to_response(record)


@router.get("/commands")
async def list_commands() -> list[CommandResponse]:
    return [_to_response(r) for r in _sm().list_commands()]


@router.get("/commands/{command_id}")
async def get_command(command_id: str) -> CommandResponse:
    record = _sm().get_command(command_id)
    if not record:
        raise HTTPException(status_code=404, detail="command not found")
    return _to_response(record)


@router.delete("/commands/{command_id}")
async def cancel_command(command_id: str) -> CommandResponse:
    record = await _sm().cancel_command(command_id)
    if not record:
        raise HTTPException(status_code=404, detail="command not found")
    return _to_response(record)
