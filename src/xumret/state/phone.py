"""PhoneState — pure state container for one phone's commands.

Sync methods only. Holds CommandRecords, applies transitions, emits SSE events.
No executor, no orchestration logic.
"""

from __future__ import annotations

import asyncio
import time

import ihate_work.o11y as o11y

from xumret.executor.models import PhoneCommand, PhoneCommandDaemonHandle, PhoneCommandResult
from xumret.state.models import CommandRecord, CommandStatus, StateEvent

logger, *_ = o11y.get_o11y(__name__)


class PhoneState:
    def __init__(self) -> None:
        self._commands: dict[str, CommandRecord] = {}
        self._daemon_to_command: dict[str, str] = {}
        self._subscribers: list[asyncio.Queue[StateEvent]] = []

    # --- queries ---

    def get(self, command_id: str) -> CommandRecord | None:
        return self._commands.get(command_id)

    def list(self) -> list[CommandRecord]:
        return list(self._commands.values())

    # --- mutations ---

    def create(self, *, command_id: str, phone_command: PhoneCommand) -> CommandRecord:
        now = time.time()
        record = CommandRecord(
            command_id=command_id,
            phone_command=phone_command,
            created_at=now,
            updated_at=now,
        )
        self._commands[command_id] = record
        self._emit("command_submitted", record)
        return record

    def set_running(self, command_id: str) -> None:
        record = self._commands[command_id]
        record.status = CommandStatus.running
        record.updated_at = time.time()
        logger.debug("state transition", command_id=command_id, status="running")
        self._emit("command_running", record)

    def set_completed(self, command_id: str, *, result: PhoneCommandResult) -> None:
        record = self._commands[command_id]
        record.status = CommandStatus.completed
        record.result = result
        record.updated_at = time.time()
        logger.info("state transition", command_id=command_id, status="completed")
        self._emit("command_completed", record)

    def set_failed(self, command_id: str, *, error: str) -> None:
        record = self._commands[command_id]
        record.status = CommandStatus.failed
        record.error = error
        record.updated_at = time.time()
        logger.warning("state transition", command_id=command_id, status="failed", error=error)
        self._emit("command_failed", record)

    def set_cancelled(self, command_id: str) -> None:
        record = self._commands[command_id]
        record.status = CommandStatus.cancelled
        record.updated_at = time.time()
        logger.info("state transition", command_id=command_id, status="cancelled")
        self._emit("command_cancelled", record)

    def set_daemon_started(
        self, command_id: str, *, handle: PhoneCommandDaemonHandle
    ) -> None:
        record = self._commands[command_id]
        record.daemon_handle = handle
        record.updated_at = time.time()
        self._daemon_to_command[handle.handle_id] = command_id
        logger.info("state transition", command_id=command_id, status="daemon_started",
                     handle_id=handle.handle_id)
        self._emit("daemon_started", record)

    def set_daemon_ended(self, handle_id: str) -> None:
        command_id = self._daemon_to_command.get(handle_id)
        if command_id and command_id in self._commands:
            record = self._commands[command_id]
            record.status = CommandStatus.completed
            record.updated_at = time.time()
            logger.info("state transition", command_id=command_id, status="daemon_ended",
                         handle_id=handle_id)
            self._emit("daemon_ended", record)

    # --- SSE subscriptions ---

    def subscribe(self) -> asyncio.Queue[StateEvent]:
        queue: asyncio.Queue[StateEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[StateEvent]) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    # --- internal ---

    def _emit(self, event_type: str, record: CommandRecord) -> None:
        event = StateEvent(
            type=event_type,
            command_id=record.command_id,
            data=record.model_dump(),
        )
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
