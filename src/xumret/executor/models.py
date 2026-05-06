"""What runs on the phone.

A PhoneCommand defines a pipeline of one or more processes and how they connect.

Two variants controlled by the `daemon` flag:
- One-shot (daemon=False, default): runs the pipeline, waits for all processes to exit,
  returns PhoneCommandResult with exit codes and outputs.
- Daemon (daemon=True): starts the pipeline and returns PhoneCommandDaemonHandle immediately.
  The handle can be queried for latest status, or used to end the processes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# --- Pipeline definition ---


class ProcessStep(BaseModel):
    argv: list[str]


class Pipe(BaseModel):
    """stdout of previous step -> stdin of next step."""

    type: Literal["pipe"] = "pipe"


class TempFile(BaseModel):
    """Previous step writes to a temp file, next step reads it."""

    type: Literal["temp_file"] = "temp_file"


Connection = Pipe | TempFile
# future: NamedPipe, Socket, ...


class PhoneCommand(BaseModel):
    name: str
    steps: list[ProcessStep]  # 1 or more processes
    connections: list[Connection]  # len == len(steps) - 1
    daemon: bool = False


# --- One-shot result (returned after all processes exit) ---


class ProcessResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str


class PhoneCommandResult(BaseModel):
    command_id: str
    steps: list[ProcessResult]  # one per ProcessStep


# --- Daemon handle (returned immediately when daemon=True) ---


class PhoneCommandDaemonHandle(BaseModel):
    command_id: str
    handle_id: str


class DaemonProcessStatus(BaseModel):
    running: bool
    exit_code: int | None = None  # None while running
    stdout_tail: str = ""  # latest output
    stderr_tail: str = ""


class DaemonStatus(BaseModel):
    handle_id: str
    steps: list[DaemonProcessStatus]  # one per ProcessStep
    all_running: bool
