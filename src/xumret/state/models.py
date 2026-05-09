"""State data types — Run lifecycle, transition events, output events.

A `Run` is observed via two event categories:

- `RunStateEvent` — discriminated union of lifecycle transitions
  (created, step_started, step_exited, running, completed, failed,
  cancelled, daemon_started, daemon_status, daemon_ended).
- `RunOutputEvent` — incremental stdout/stderr for one step's fd.

The materialized snapshot of a Run is `RunRecord` (status + per-step
state + transition log).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from xumret.executor.models import PhoneCommand


# --- Status ---


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
)


# --- State events ---


class _RunStateBase(BaseModel):
    slug: str
    at: float


class RunStateCreated(_RunStateBase):
    type: Literal["created"] = "created"


class RunStateStepStarted(_RunStateBase):
    type: Literal["step_started"] = "step_started"
    step_index: int
    pid: int


class RunStateStepExited(_RunStateBase):
    type: Literal["step_exited"] = "step_exited"
    step_index: int
    exit_code: int


class RunStateRunning(_RunStateBase):
    type: Literal["running"] = "running"


class RunStateCompleted(_RunStateBase):
    type: Literal["completed"] = "completed"


class RunStateFailed(_RunStateBase):
    type: Literal["failed"] = "failed"
    error: str


class RunStateCancelled(_RunStateBase):
    type: Literal["cancelled"] = "cancelled"


class RunStateDaemonStarted(_RunStateBase):
    type: Literal["daemon_started"] = "daemon_started"


class RunStateDaemonStatus(_RunStateBase):
    type: Literal["daemon_status"] = "daemon_status"
    all_running: bool
    step_running: list[bool]


class RunStateDaemonEnded(_RunStateBase):
    type: Literal["daemon_ended"] = "daemon_ended"


RunStateEvent = (
    RunStateCreated
    | RunStateStepStarted
    | RunStateStepExited
    | RunStateRunning
    | RunStateCompleted
    | RunStateFailed
    | RunStateCancelled
    | RunStateDaemonStarted
    | RunStateDaemonStatus
    | RunStateDaemonEnded
)


# --- Output events ---


class RunOutputEvent(BaseModel):
    type: Literal["output"] = "output"
    slug: str
    at: float
    step_index: int
    fd: Literal["stdout", "stderr"]
    # Lines mode: decoded UTF-8 strings (no trailing newline)
    lines: list[str] | None = None
    # Binary mode: base64-encoded bytes
    bytes: str | None = None
    # Drop deltas since the previous event for this fd
    dropped_lines: int | None = None
    dropped_bytes: int | None = None


RunEvent = RunStateEvent | RunOutputEvent


# --- Materialized snapshot ---


class StepState(BaseModel):
    pid: int | None = None
    exit_code: int | None = None
    # Bounded tail (lines mode: decoded text; binary mode: not stored — see Run).
    stdout_tail: str = ""
    stderr_tail: str = ""
    stdout_dropped: int = 0
    stderr_dropped: int = 0


class RunRecord(BaseModel):
    """Materialized snapshot of a Run; also serves as the API response shape."""

    slug: str
    phone_command: PhoneCommand
    status: RunStatus
    created_at: float
    updated_at: float
    error: str | None = None
    daemon_started: bool = False
    daemon_ended: bool = False
    steps: list[StepState]
    transitions: list[RunStateEvent] = []
