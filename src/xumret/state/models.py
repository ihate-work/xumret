"""State data types — command tracking, handles, and SSE events."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from xumret.executor.models import (
    PhoneCommand,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
)


class CommandStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CommandRecord(BaseModel):
    command_id: str
    phone_command: PhoneCommand
    status: CommandStatus = CommandStatus.pending
    result: PhoneCommandResult | None = None
    daemon_handle: PhoneCommandDaemonHandle | None = None
    error: str | None = None
    created_at: float
    updated_at: float


class CommandHandle(BaseModel):
    """Lightweight receipt returned from submit."""

    command_id: str
    status: CommandStatus
    created_at: float


class StateEvent(BaseModel):
    """Pushed to SSE subscribers on every state transition."""

    type: str
    command_id: str
    data: dict[str, Any]
