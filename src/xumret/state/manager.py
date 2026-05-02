"""StateManager — command lifecycle tracking and event bus.

Holds an Executor (via protocol), tracks submitted commands, caches results,
and emits events for SSE subscribers.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Literal

import ihate_work.o11y as o11y
from pydantic import BaseModel

from xumret.executor.models import (
    PhoneCommand,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
)
from xumret.executor.protocol import Executor
from xumret.server_bridge.models import (
    CancelCommand,
    CommandError,
    EndDaemon,
    QueryDaemon,
    SubmitCommand,
    SubmitDaemonStarted,
    SubmitOneshotResult,
)

logger, *_ = o11y.get_o11y(__name__)

CommandStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class CommandRecord(BaseModel):
    command_id: str
    phone_command: PhoneCommand
    status: CommandStatus = "pending"
    result: PhoneCommandResult | None = None
    daemon_handle: PhoneCommandDaemonHandle | None = None
    error: str | None = None
    created_at: float
    updated_at: float


class StateEvent(BaseModel):
    type: str
    command_id: str
    data: dict[str, Any]


class StateManager:
    def __init__(self, *, executor: Executor):
        self._executor = executor
        self._commands: dict[str, CommandRecord] = {}
        self._subscribers: list[asyncio.Queue[StateEvent]] = []

    # ── Public API (called by routes) ────────────────────────────────

    async def submit_command(self, phone_command: PhoneCommand) -> CommandRecord:
        command_id = str(uuid.uuid4())
        now = time.time()
        record = CommandRecord(
            command_id=command_id,
            phone_command=phone_command,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self._commands[command_id] = record
        self._emit("command_submitted", record)
        asyncio.create_task(self._execute(record))
        return record

    def get_command(self, command_id: str) -> CommandRecord | None:
        return self._commands.get(command_id)

    def list_commands(self) -> list[CommandRecord]:
        return list(self._commands.values())

    async def cancel_command(self, command_id: str) -> CommandRecord | None:
        record = self._commands.get(command_id)
        if not record:
            return None
        if record.status in ("completed", "failed", "cancelled"):
            return record

        await self._executor.cancel(CancelCommand(command_id=command_id))

        # If it was a daemon, end it
        if record.daemon_handle:
            await self._executor.end_daemon(EndDaemon(handle_id=record.daemon_handle.handle_id))

        record.status = "cancelled"
        record.updated_at = time.time()
        self._emit("command_cancelled", record)
        return record

    async def query_daemon(self, handle_id: str) -> dict[str, Any]:
        report = await self._executor.query_daemon(QueryDaemon(handle_id=handle_id))
        return report.model_dump()

    # ── Event bus ────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue[StateEvent]:
        q: asyncio.Queue[StateEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[StateEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def _emit(self, event_type: str, record: CommandRecord) -> None:
        event = StateEvent(
            type=event_type,
            command_id=record.command_id,
            data=record.model_dump(),
        )
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("subscriber queue full, dropping event")

    # ── Background execution ─────────────────────────────────────────

    async def _execute(self, record: CommandRecord) -> None:
        record.status = "running"
        record.updated_at = time.time()
        self._emit("command_running", record)

        submit_cmd = SubmitCommand(
            command_id=record.command_id,
            phone_command=record.phone_command,
        )

        try:
            result = await self._executor.submit(submit_cmd)
        except Exception as e:
            logger.exception("executor error", command_id=record.command_id, error=str(e))
            record.status = "failed"
            record.error = str(e)
            record.updated_at = time.time()
            self._emit("command_failed", record)
            return

        if isinstance(result, SubmitOneshotResult):
            record.status = "completed"
            record.result = result.result
        elif isinstance(result, SubmitDaemonStarted):
            record.daemon_handle = result.handle
            # stays "running"
        elif isinstance(result, CommandError):
            record.status = "failed"
            record.error = result.error
        else:
            record.status = "failed"
            record.error = "unexpected_result"

        record.updated_at = time.time()
        self._emit("command_updated", record)
