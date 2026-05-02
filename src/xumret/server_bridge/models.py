"""The command protocol between state manager and executor.

BridgeCommand is the base for all messages. Used over WS in server-executor mode,
and as plain in-process objects in single mode.

One-shot flow: submit blocks until all processes exit, returns SubmitOneshotResult.
Daemon flow: submit returns SubmitDaemonStarted immediately. Caller uses
query_daemon to poll status, end_daemon to terminate.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from xumret.executor.models import (
    DaemonStatus,
    PhoneCommand,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
    ProcessResult,
)


class BridgeCommand(BaseModel):
    type: str


# --- Server -> Executor ---


class SubmitCommand(BridgeCommand):
    type: Literal["submit"] = "submit"
    command_id: str
    phone_command: PhoneCommand  # daemon flag is on PhoneCommand


class CancelCommand(BridgeCommand):
    type: Literal["cancel"] = "cancel"
    command_id: str


class QueryStatus(BridgeCommand):
    type: Literal["query_status"] = "query_status"
    command_id: str


class QueryDaemon(BridgeCommand):
    type: Literal["query_daemon"] = "query_daemon"
    handle_id: str


class EndDaemon(BridgeCommand):
    type: Literal["end_daemon"] = "end_daemon"
    handle_id: str


# --- Executor -> Server ---


class SubmitOneshotResult(BridgeCommand):
    type: Literal["oneshot_result"] = "oneshot_result"
    result: PhoneCommandResult


class SubmitDaemonStarted(BridgeCommand):
    type: Literal["daemon_started"] = "daemon_started"
    handle: PhoneCommandDaemonHandle


class DaemonStatusReport(BridgeCommand):
    type: Literal["daemon_status"] = "daemon_status"
    status: DaemonStatus


class DaemonEnded(BridgeCommand):
    type: Literal["daemon_ended"] = "daemon_ended"
    handle_id: str
    final_steps: list[ProcessResult]  # final exit codes + outputs


class CommandError(BridgeCommand):
    type: Literal["error"] = "error"
    command_id: str
    error: str
