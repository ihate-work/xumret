"""What runs on the phone.

A PhoneCommand defines a pipeline of one or more processes and how they connect.

Lifecycle is uniform: pending → running → completed / failed / cancelled.
`RunOption.timeout` bounds how long the pipeline may run; absence means "no
time bound" — which, combined with `mutex_by_slug`, is how callers express
daemon-like commands (the frontend uses that combo as a UI heuristic).

The executor emits per-step events; consumers observe the run through the
`Run` abstraction (see `xumret.state.run`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class StreamConfig(BaseModel):
    """How to handle one stream of a step.

    Two options that can mix:
    - forward to another step's stdin (`forward_dest_process_idx`)
    - capture via temp file on the executor (expected use: to reap the last
      step, or to debug). Never piped into executor memory.

    A stream that is neither captured nor forwarded is implicitly dropped.
    """

    mode: Literal["lines", "binary"] = "lines"
    # capture: executor writes the stream to a temp file and surfaces it in events.
    capture: bool = False
    # forward to stdin of steps[forward_dest_process_idx].
    # Executor validates that the resulting graph is well-formed.
    forward_dest_process_idx: int | None = None


class CommandStep(BaseModel):
    """One process in a pipeline."""

    argv: list[str]
    stdout_stream: StreamConfig = StreamConfig()
    stderr_stream: StreamConfig = StreamConfig()


class RunOption(BaseModel):
    """Caller-declared policy for a Run. TODO: rename to RunConfig"""

    # timeout: max wall-clock seconds before the executor cancels the run.
    # None = no time bound. (mutex_by_slug + timeout=None is the daemon shape.)
    timeout: float | None = None
    # slug: a caller-provided identifier for the run
    # can be used to dedup commands that don't need multiple running instances
    slug: str | None = None
    # when True: don't run the command if another live run exists with the same slug; instead raise SubmitConflict.
    mutex_by_slug: bool = False


class PhoneCommand(BaseModel):
    # name: non-unique title
    name: str
    # desc: non-unique longer description
    desc: str | None = None
    steps: list[CommandStep]
    run_option: RunOption = RunOption()
