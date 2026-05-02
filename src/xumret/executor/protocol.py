"""The abstraction boundary between state management and command execution.

StateManager depends only on the Executor protocol. It does not know or care
which implementation it holds:
- LocalExecutor: runs subprocesses directly (single mode)
- RemoteExecutor: forwards over WS via server_bridge (server-executor mode)
"""

from __future__ import annotations

from typing import Protocol

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

SubmitResponse = SubmitOneshotResult | SubmitDaemonStarted | CommandError


class Executor(Protocol):
    async def submit(self, cmd: SubmitCommand) -> SubmitResponse: ...
    async def cancel(self, cmd: CancelCommand) -> None: ...
    async def query_status(self, cmd: QueryStatus) -> DaemonStatusReport | CommandError: ...
    async def query_daemon(self, cmd: QueryDaemon) -> DaemonStatusReport: ...
    async def end_daemon(self, cmd: EndDaemon) -> DaemonEnded: ...
