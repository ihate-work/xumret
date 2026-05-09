"""What runs on the phone.

A PhoneCommand defines a pipeline of one or more processes and how they connect.

`daemon=False`: pipeline runs to completion; lifecycle goes
pending → running → completed / failed / cancelled.

`daemon=True`: pipeline starts and stays alive; lifecycle adds
daemon_started / daemon_ended events on top.

Either way the executor emits per-step events; consumers observe the run
through the `Run` abstraction (see `xumret.state.run`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class StreamConfig(BaseModel):
    """How to read and frame one fd of one ProcessStep."""

    mode: Literal["lines", "binary"] = "lines"
    back_pressure: bool = False


class ProcessStep(BaseModel):
    argv: list[str]
    stdout_stream: StreamConfig = StreamConfig()
    stderr_stream: StreamConfig = StreamConfig()


class Pipe(BaseModel):
    """stdout of previous step -> stdin of next step."""

    type: Literal["pipe"] = "pipe"


class TempFile(BaseModel):
    """Previous step writes to a temp file, next step reads it."""

    type: Literal["temp_file"] = "temp_file"


Connection = Pipe | TempFile


class RunOption(BaseModel):
    """Caller-declared identity and dedup policy for a Run."""

    slug: str | None = None
    mutex_by_slug: bool = False


class PhoneCommand(BaseModel):
    name: str
    steps: list[ProcessStep]
    connections: list[Connection]  # len == len(steps) - 1
    daemon: bool = False
    run_option: RunOption = RunOption()
