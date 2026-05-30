"""Tests for SingleMain — the single-mode XumretService implementation."""

from __future__ import annotations

import asyncio
import time

import pytest

from xumret.executor.dummy_executor import DummyExecutor
from xumret.executor.models import CommandStep, PhoneCommand, RunOption
from xumret.protocol.executor import Executor
from xumret.single import SingleMain
from xumret.state.models import RunStateCompleted, RunStateFailed
from xumret.state.phone import PhoneState
from xumret.state.run import Run


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _pc(slug: str | None = "X") -> PhoneCommand:
    return PhoneCommand(
        name="t",
        steps=[CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(slug=slug),
    )


class _BlockingExecutor(Executor):
    """Awaits forever inside `run` so the task stays live until cancelled."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stopped_slugs: list[str] = []
        self.shutdown_called = False

    async def run(self, run: Run) -> None:
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    async def stop(self, slug: str) -> None:
        self.stopped_slugs.append(slug)

    async def shutdown(self) -> None:
        self.shutdown_called = True

    async def step_stdout_bytes(self, slug: str, step_index: int) -> bytes | None:  # pragma: no cover - unused
        return None


class _CrashingExecutor(Executor):
    """`run` raises after a tick to exercise `_drive`'s except-Exception path."""

    async def run(self, run: Run) -> None:
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    async def stop(self, slug: str) -> None:  # pragma: no cover - unused
        pass

    async def shutdown(self) -> None:  # pragma: no cover - unused
        pass

    async def step_stdout_bytes(self, slug: str, step_index: int) -> bytes | None:  # pragma: no cover - unused
        return None


# --- list_devices ---


@pytest.mark.anyio
async def test_list_devices_returns_host() -> None:
    svc = SingleMain(executor=DummyExecutor(), state=PhoneState())
    devices = await svc.list_devices()
    assert len(devices) == 1
    assert devices[0].id == devices[0].name


# --- stop on a live run ---


@pytest.mark.anyio
async def test_stop_on_live_run_calls_executor_stop() -> None:
    state = PhoneState()
    executor = _BlockingExecutor()
    svc = SingleMain(executor=executor, state=state)
    record = await svc.submit(_pc("X"))
    assert record.slug == "X"
    await executor.started.wait()

    result = await svc.stop("X")
    assert result is not None
    assert "X" in executor.stopped_slugs

    # Cleanup: cancel the background task so the test loop exits cleanly.
    await svc.shutdown()


# --- subscribe / unsubscribe ---


def test_subscribe_returns_queue_and_unsubscribe_removes_it() -> None:
    state = PhoneState()
    svc = SingleMain(executor=DummyExecutor(), state=state)
    q = svc.subscribe()
    assert q in state._subscribers
    svc.unsubscribe(q)
    assert q not in state._subscribers


# --- shutdown ---


@pytest.mark.anyio
async def test_shutdown_cancels_inflight_tasks_and_calls_executor() -> None:
    state = PhoneState()
    executor = _BlockingExecutor()
    svc = SingleMain(executor=executor, state=state)
    await svc.submit(_pc("X"))
    await executor.started.wait()

    task = svc._tasks["X"]
    assert not task.done()
    await svc.shutdown()
    # Give the loop a moment to settle the cancellation.
    await asyncio.sleep(0)
    assert task.done()
    assert executor.shutdown_called


# --- cache_for: re-submit must not re-drive ---


class _CountingExecutor(Executor):
    """Records how many times `run` is invoked, completes immediately."""

    def __init__(self) -> None:
        self.run_calls = 0

    async def run(self, run: Run) -> None:
        self.run_calls += 1
        run.emit(RunStateCompleted(slug=run.slug, at=time.time()))

    async def stop(self, slug: str) -> None:  # pragma: no cover - unused
        pass

    async def shutdown(self) -> None:  # pragma: no cover - unused
        pass

    async def step_stdout_bytes(self, slug: str, step_index: int) -> bytes | None:  # pragma: no cover - unused
        return None


@pytest.mark.anyio
async def test_cache_hit_resubmit_does_not_redrive() -> None:
    """A `cache_for` hit must not spawn a new driver task.

    Re-driving a cached terminal run would make `LocalExecutor.run` mkdtemp a
    fresh tmpdir, clobbering the captured stdout from the original run — the
    next `step_stdout_bytes` would then read an empty file. Regression for
    "camera-info produced no stdout" on second page-open.
    """
    state = PhoneState()
    executor = _CountingExecutor()
    svc = SingleMain(executor=executor, state=state)

    pc = PhoneCommand(
        name="t",
        steps=[CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(slug="X", cache_for=600),
    )

    first = await svc.submit(pc)
    # Let the driver complete.
    await svc._tasks["X"]
    assert first.slug == "X"
    assert executor.run_calls == 1

    # Second submit within cache_for window must be served from cache without
    # re-driving the executor.
    second = await svc.submit(pc)
    assert second.slug == "X"
    assert executor.run_calls == 1, "cache hit should not invoke executor.run again"


# --- _drive exception handling ---


@pytest.mark.anyio
async def test_drive_emits_failed_when_executor_crashes() -> None:
    state = PhoneState()
    svc = SingleMain(executor=_CrashingExecutor(), state=state)
    await svc.submit(_pc("X"))
    # Give the driver task a tick to run and crash.
    for _ in range(10):
        await asyncio.sleep(0.01)
        run = state.get("X")
        if run is not None and run.is_terminal:
            break
    run = state.get("X")
    assert run is not None
    assert run.status.value == "failed"
    rec = run.record
    assert rec.error == "boom"
