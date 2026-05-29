"""SingleMain — single mode orchestrator.

Implements `XumretService`. Owns one `LocalExecutor` (or `DummyExecutor`)
and one `PhoneState`. Submitting a `PhoneCommand` registers a `Run` in
`PhoneState` and hands it to the executor as a background task.

`SingleMain` and `PhoneState` are independent — a future multi-device
orchestrator (`HubMain`) will hold many `PhoneState`s.
"""

from __future__ import annotations

import asyncio
import socket
import time

import ihate_work.o11y as o11y

from xumret.executor.models import PhoneCommand
from xumret.protocol.device import Device
from xumret.protocol.executor import Executor
from xumret.state.models import RunEvent, RunRecord, RunStateFailed
from xumret.state.phone import (
    PhoneState,
    StillLive,
    SubmitConflict,
    UnknownSlug,
)
from xumret.state.run import Run

logger, *_ = o11y.get_o11y(__name__)


class SingleMain:
    def __init__(self, *, executor: Executor, state: PhoneState) -> None:
        self._executor = executor
        self._state = state
        self._tasks: dict[str, asyncio.Task] = {}

    async def shutdown(self) -> None:
        for slug, task in list(self._tasks.items()):
            if not task.done():
                logger.info("shutdown: cancelling task", slug=slug)
                task.cancel()
        if hasattr(self._executor, "shutdown"):
            await self._executor.shutdown()

    # --- XumretService interface ---

    async def list_devices(self) -> list[Device]:
        host = socket.gethostname()
        return [Device(id=host, name=host)]

    async def submit(self, phone_command: PhoneCommand) -> RunRecord:
        run = self._state.submit(phone_command)
        # If submit returned an existing live run (idempotent join), don't restart.
        if run.slug not in self._tasks or self._tasks[run.slug].done():
            self._tasks[run.slug] = asyncio.create_task(
                self._drive(run), name=f"run[{run.slug}]",
            )
        return run.record

    async def get(self, slug: str) -> RunRecord | None:
        run = self._state.get(slug)
        return _slim(run) if run else None

    async def list(self) -> list[RunRecord]:
        return [_slim(r) for r in self._state.list()]

    async def get_state(self, slug: str) -> RunRecord | None:
        run = self._state.get(slug)
        return run.record if run else None

    async def stop(self, slug: str) -> RunRecord | None:
        run = self._state.get(slug)
        if run is None:
            return None
        if run.is_live:
            await self._executor.stop(slug)
        return _slim(run)

    async def reap(self, slug: str) -> bool:
        try:
            self._state.reap(slug)
        except UnknownSlug:
            return False
        except StillLive:
            raise
        self._tasks.pop(slug, None)
        return True

    async def step_stdout_bytes(self, slug: str, step_index: int) -> bytes | None:
        if self._state.get(slug) is None:
            return None
        return await self._executor.step_stdout_bytes(slug, step_index)

    def subscribe(self) -> asyncio.Queue[RunEvent]:
        return self._state.subscribe()

    def unsubscribe(self, queue: asyncio.Queue[RunEvent]) -> None:
        self._state.unsubscribe(queue)

    # --- background execution ---

    async def _drive(self, run: Run) -> None:
        try:
            await self._executor.run(run)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("executor crashed", slug=run.slug)
            if run.is_live:
                run.emit(RunStateFailed(slug=run.slug, at=time.time(), error=str(exc)))


# --- helpers ---


def _slim(run: Run) -> RunRecord:
    """Slim view: full record without the transition log."""
    rec = run.record
    return rec.model_copy(update={"transitions": []})


# Re-export for routes layer (HTTP error mapping).
__all__ = ["SingleMain", "SubmitConflict", "UnknownSlug", "StillLive"]
