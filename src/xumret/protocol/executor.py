"""Boundary between phone-state orchestration and command execution.

The executor is given a `Run` and drives it forward by emitting events
(`run.emit(...)`). It produces no return value — observers read the run's
materialized record or subscribe to its event stream.

Implementations:
- `LocalExecutor`: spawns subprocesses on this machine.
- `RemoteExecutor` (deferred): forwards events over a WS bridge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from xumret.state.run import Run


class Executor(ABC):
    @abstractmethod
    async def run(self, run: Run) -> None:
        """Drive the run to a terminal state, emitting events along the way."""

    @abstractmethod
    async def stop(self, slug: str) -> None:
        """Signal cancellation to a live run. No-op if unknown or already terminal."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Best-effort shutdown of all in-flight runs."""

    @abstractmethod
    async def step_stdout_bytes(self, slug: str, step_index: int) -> bytes | None:
        """Return the full captured stdout for one step, or None if unknown.

        Distinct from `Run.steps[i].stdout_tail`, which is a bounded in-memory
        tail meant for live observation. This is the *full* captured payload,
        intended for one-shot query commands whose entire output is the result
        (e.g. `termux-camera-info`, `termux-sms-list`).
        """
