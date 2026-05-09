from __future__ import annotations

import asyncio
import json

from xumret.executor.dummy_executor import DummyExecutor
from xumret.executor.models import PhoneCommand, ProcessStep
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateDaemonStarted,
    RunStateStepExited,
    RunStateStepStarted,
    RunStatus,
)
from xumret.state.run import Run


def _run(*, daemon: bool = False, argv: list[str] | None = None,
         steps: int = 1) -> Run:
    if argv is not None:
        step_list = [ProcessStep(argv=argv)]
    else:
        step_list = [ProcessStep(argv=["echo", "hi"]) for _ in range(steps)]
    pc = PhoneCommand(name="t", steps=step_list, connections=[], daemon=daemon)
    return Run(slug="s", phone_command=pc)


def _types(run: Run) -> list[str]:
    return [t.type for t in run.record.transitions]


def test_oneshot_emits_running_through_completed() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(steps=2)
        await ex.run(run)
        assert run.status == RunStatus.completed
        types = _types(run)
        assert types[0] == "running"
        assert types.count("step_started") == 2
        assert types.count("step_exited") == 2
        assert types[-1] == "completed"
    asyncio.run(go())


def test_canned_battery_status_emits_output() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(argv=["termux-battery-status"])
        await ex.run(run)
        tail = run.record.steps[0].stdout_tail
        data = json.loads(tail)
        assert data["percentage"] == 72
    asyncio.run(go())


def test_silent_command_emits_no_output() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(argv=["termux-toast", "hello"])
        await ex.run(run)
        assert run.record.steps[0].stdout_tail == ""
        assert run.status == RunStatus.completed
    asyncio.run(go())


def test_unknown_binary_returns_stub() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(argv=["my-script", "--flag"])
        await ex.run(run)
        data = json.loads(run.record.steps[0].stdout_tail)
        assert data["dummy"] is True
        assert data["argv"] == ["my-script", "--flag"]
    asyncio.run(go())


def test_daemon_emits_started_then_blocks_until_stop() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(daemon=True)
        task = asyncio.create_task(ex.run(run))
        # Give it time to spawn
        await asyncio.sleep(0.05)
        assert any(isinstance(t, RunStateDaemonStarted) for t in run.record.transitions)
        assert run.is_live
        await ex.stop("s")
        await asyncio.wait_for(task, timeout=1.0)
        assert run.status == RunStatus.cancelled
    asyncio.run(go())


def test_subscriber_sees_step_events_in_order() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(argv=["termux-battery-status"])
        q = run.subscribe()
        await ex.run(run)
        seen: list[type] = []
        while not q.empty():
            seen.append(type(q.get_nowait()))
        # Order: running, step_started, output, step_exited, completed
        assert RunStateStepStarted in seen
        assert RunOutputEvent in seen
        assert RunStateStepExited in seen
        assert RunStateCompleted in seen
        # step_started must precede step_exited
        ss = seen.index(RunStateStepStarted)
        se = seen.index(RunStateStepExited)
        assert ss < se
    asyncio.run(go())


def test_stop_unknown_slug_is_noop() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        await ex.stop("nope")
    asyncio.run(go())


def test_shutdown_cancels_inflight_daemons() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(daemon=True)
        task = asyncio.create_task(ex.run(run))
        await asyncio.sleep(0.05)
        await ex.shutdown()
        await asyncio.wait_for(task, timeout=1.0)
        assert run.status == RunStatus.cancelled
        # cancelled is a transition event
        assert any(isinstance(t, RunStateCancelled) for t in run.record.transitions)
    asyncio.run(go())
