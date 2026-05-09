"""SingleMain — single mode orchestrator.

Implements XumretService. Owns one Executor and one PhoneState.
Accepts commands, runs them in background tasks, drives state transitions.
"""

from __future__ import annotations

import asyncio
import uuid

import ihate_work.o11y as o11y

from xumret.executor.models import PhoneCommand
from xumret.protocol.executor import Executor
from xumret.server_bridge.models import (
    CancelCommand,
    DaemonEnded,
    DaemonStatusReport,
    EndDaemon,
    QueryDaemon,
    SubmitCommand,
    SubmitDaemonStarted,
    SubmitOneshotResult,
)
from xumret.state.models import CommandHandle, CommandRecord, StateEvent
from xumret.state.phone import PhoneState

logger, *_ = o11y.get_o11y(__name__)


class SingleMain:
    def __init__(self, *, executor: Executor, state: PhoneState) -> None:
        self._executor = executor
        self._state = state
        self._tasks: dict[str, asyncio.Task] = {}

    async def shutdown(self) -> None:
        """Cancel in-flight tasks and shut down the executor."""
        for cid, task in self._tasks.items():
            if not task.done():
                logger.info("shutdown: cancelling task", command_id=cid)
                task.cancel()
        if hasattr(self._executor, "shutdown"):
            await self._executor.shutdown()

    # --- XumretService interface ---

    async def submit(self, phone_command: PhoneCommand) -> CommandHandle:
        command_id = uuid.uuid4().hex[:12]
        record = self._state.create(command_id=command_id, phone_command=phone_command)
        self._tasks[command_id] = asyncio.create_task(self._run(command_id))
        return CommandHandle(
            command_id=record.command_id,
            status=record.status,
            created_at=record.created_at,
        )

    async def get(self, command_id: str) -> CommandRecord | None:
        return self._state.get(command_id)

    async def list(self) -> list[CommandRecord]:
        return self._state.list()

    async def cancel(self, command_id: str) -> CommandRecord | None:
        record = self._state.get(command_id)
        if not record:
            return None
        task = self._tasks.get(command_id)
        if task and not task.done():
            task.cancel()
        await self._executor.cancel(CancelCommand(command_id=command_id))
        self._state.set_cancelled(command_id)
        return self._state.get(command_id)

    async def query_daemon(self, handle_id: str) -> DaemonStatusReport:
        return await self._executor.query_daemon(QueryDaemon(handle_id=handle_id))

    async def end_daemon(self, handle_id: str) -> DaemonEnded:
        result = await self._executor.end_daemon(EndDaemon(handle_id=handle_id))
        self._state.set_daemon_ended(handle_id)
        return result

    def subscribe(self) -> asyncio.Queue[StateEvent]:
        return self._state.subscribe()

    def unsubscribe(self, queue: asyncio.Queue[StateEvent]) -> None:
        self._state.unsubscribe(queue)

    # --- background execution ---

    async def _run(self, command_id: str) -> None:
        self._state.set_running(command_id)
        record = self._state.get(command_id)
        assert record is not None

        cmd = SubmitCommand(command_id=command_id, phone_command=record.phone_command)
        try:
            response = await self._executor.submit(cmd)
        except Exception as exc:
            self._state.set_failed(command_id, error=str(exc))
            logger.error("command_execution_failed", command_id=command_id, error=str(exc))
            return

        if isinstance(response, SubmitOneshotResult):
            self._state.set_completed(command_id, result=response.result)
        elif isinstance(response, SubmitDaemonStarted):
            self._state.set_daemon_started(command_id, handle=response.handle)
        else:  # CommandError
            self._state.set_failed(command_id, error=response.error)
