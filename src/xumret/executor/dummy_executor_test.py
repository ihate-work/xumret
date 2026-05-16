from __future__ import annotations

import asyncio
import json

from xumret.executor.dummy_executor import DummyExecutor
from xumret.executor.models import (
    CommandStep,
    PhoneCommand,
    StreamConfig,
)
from xumret.state.models import (
    RunOutputEvent,
    RunStateCompleted,
    RunStateStepExited,
    RunStateStepStarted,
    RunStatus,
)
from xumret.state.run import Run


def _captured(argv: list[str]) -> CommandStep:
    return CommandStep(argv=argv, stdout_stream=StreamConfig(capture=True))


def _run(*, argv: list[str] | None = None, steps: int = 1, capture: bool = True) -> Run:
    if argv is not None:
        step_list = [_captured(argv) if capture else CommandStep(argv=argv)]
    else:
        make = _captured if capture else (lambda a: CommandStep(argv=a))
        step_list = [make(["echo", "hi"]) for _ in range(steps)]
    pc = PhoneCommand(name="t", steps=step_list)
    return Run(slug="s", phone_command=pc)


def _types(run: Run) -> list[str]:
    return [t.type for t in run.record.transitions]


def test_oneshot_emits_running_through_completed() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(steps=2, capture=False)
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


def test_capture_disabled_means_no_output_event() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        run = _run(argv=["termux-battery-status"], capture=False)
        await ex.run(run)
        assert run.record.steps[0].stdout_tail == ""
        assert run.status == RunStatus.completed
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
        assert RunStateStepStarted in seen
        assert RunOutputEvent in seen
        assert RunStateStepExited in seen
        assert RunStateCompleted in seen
        ss = seen.index(RunStateStepStarted)
        se = seen.index(RunStateStepExited)
        assert ss < se
    asyncio.run(go())


def test_stop_unknown_slug_is_noop() -> None:
    async def go() -> None:
        ex = DummyExecutor()
        await ex.stop("nope")
    asyncio.run(go())
