"""State data types — Run lifecycle, transition events, output events.

A `Run` is observed via two event categories:

- `RunStateEvent` — discriminated union of lifecycle transitions
  (created, step_started, step_exited, running, completed, failed,
  cancelled, timed_out).
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
    timed_out = "timed_out"


TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.completed,
        RunStatus.failed,
        RunStatus.cancelled,
        RunStatus.timed_out,
    }
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


class RunStateTimedOut(_RunStateBase):
    type: Literal["timed_out"] = "timed_out"


RunStateEvent = (
    RunStateCreated
    | RunStateStepStarted
    | RunStateStepExited
    | RunStateRunning
    | RunStateCompleted
    | RunStateFailed
    | RunStateCancelled
    | RunStateTimedOut
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


RunEvent = RunStateEvent | RunOutputEvent


# --- Materialized snapshot ---


class StepState(BaseModel):
    pid: int | None = None
    exit_code: int | None = None
    # Bounded tail (lines mode: decoded text; binary mode: not stored — see Run).
    stdout_tail: str = ""
    stderr_tail: str = ""


class RunRecord(BaseModel):
    """Materialized snapshot of a Run; also serves as the API response shape."""

    slug: str
    phone_command: PhoneCommand
    status: RunStatus
    created_at: float
    updated_at: float
    error: str | None = None
    steps: list[StepState]
    transitions: list[RunStateEvent] = []
