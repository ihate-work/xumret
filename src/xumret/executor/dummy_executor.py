"""DummyExecutor — returns canned responses without spawning processes.

Used for local development and tests where real subprocess execution
is unnecessary or undesirable.
"""

from __future__ import annotations

import uuid

from xumret.executor.models import (
    DaemonProcessStatus,
    DaemonStatus,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
    ProcessResult,
)
from xumret.server_bridge.models import (
    CancelCommand,
    CommandError,
    DaemonEnded,
    DaemonStatusReport,
    EndDaemon,
    QueryDaemon,
    QueryStatus,
    SubmitCommand,
    SubmitDaemonStarted,
    SubmitOneshotResult,
)


class DummyExecutor:
    """Implements Executor protocol with fake results. No real processes are spawned."""

    def __init__(self) -> None:
        self._daemons: dict[str, str] = {}  # handle_id -> command_id
        self._cancelled: set[str] = set()  # command_ids

    async def submit(
        self, cmd: SubmitCommand
    ) -> SubmitOneshotResult | SubmitDaemonStarted | CommandError:
        pc = cmd.phone_command
        if pc.daemon:
            handle_id = str(uuid.uuid4())
            self._daemons[handle_id] = cmd.command_id
            return SubmitDaemonStarted(
                handle=PhoneCommandDaemonHandle(
                    command_id=cmd.command_id, handle_id=handle_id,
                )
            )
        return SubmitOneshotResult(
            result=PhoneCommandResult(
                command_id=cmd.command_id,
                steps=[
                    ProcessResult(exit_code=0, stdout="", stderr="")
                    for _ in pc.steps
                ],
            )
        )

    async def cancel(self, cmd: CancelCommand) -> None:
        self._cancelled.add(cmd.command_id)

    async def query_status(self, cmd: QueryStatus) -> DaemonStatusReport | CommandError:
        for handle_id, command_id in self._daemons.items():
            if command_id == cmd.command_id:
                return self._make_status(handle_id)
        return CommandError(command_id=cmd.command_id, error="not_found")

    async def query_daemon(self, cmd: QueryDaemon) -> DaemonStatusReport:
        if cmd.handle_id in self._daemons:
            return self._make_status(cmd.handle_id)
        return DaemonStatusReport(
            status=DaemonStatus(handle_id=cmd.handle_id, steps=[], all_running=False)
        )

    async def end_daemon(self, cmd: EndDaemon) -> DaemonEnded:
        self._daemons.pop(cmd.handle_id, None)
        return DaemonEnded(handle_id=cmd.handle_id, final_steps=[])

    def _make_status(self, handle_id: str) -> DaemonStatusReport:
        return DaemonStatusReport(
            status=DaemonStatus(
                handle_id=handle_id,
                steps=[DaemonProcessStatus(running=True)],
                all_running=True,
            )
        )
