from __future__ import annotations

import asyncio
import time

from xumret.executor.models import PhoneCommand, ProcessStep
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateCreated,
    RunStateFailed,
    RunStateRunning,
    RunStateStepExited,
    RunStateStepStarted,
    RunStatus,
)
from xumret.state.run import OUTPUT_TAIL_CAP, Run


def _pc(steps: int = 1) -> PhoneCommand:
    return PhoneCommand(
        name="t",
        steps=[ProcessStep(argv=["echo", "hi"]) for _ in range(steps)],
        connections=[],
    )


def _now() -> float:
    return time.time()


# --- emit + apply ---


def test_initial_state_pending():
    run = Run(slug="s", phone_command=_pc())
    assert run.status == RunStatus.pending
    assert run.is_live
    assert not run.is_terminal


def test_emit_running_transitions_status():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunStateRunning(slug="s", at=_now()))
    assert run.status == RunStatus.running


def test_emit_step_started_records_pid():
    run = Run(slug="s", phone_command=_pc(steps=2))
    run.emit(RunStateStepStarted(slug="s", at=_now(), step_index=0, pid=4242))
    assert run.record.steps[0].pid == 4242


def test_emit_step_exited_records_exit_code():
    run = Run(slug="s", phone_command=_pc(steps=2))
    run.emit(RunStateStepExited(slug="s", at=_now(), step_index=1, exit_code=3))
    assert run.record.steps[1].exit_code == 3


def test_completed_is_terminal():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunStateRunning(slug="s", at=_now()))
    run.emit(RunStateCompleted(slug="s", at=_now()))
    assert run.is_terminal
    assert run.status == RunStatus.completed


def test_failed_records_error():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunStateFailed(slug="s", at=_now(), error="boom"))
    assert run.is_terminal
    assert run.status == RunStatus.failed
    assert run.record.error == "boom"


def test_cancelled_is_terminal():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunStateCancelled(slug="s", at=_now()))
    assert run.is_terminal
    assert run.status == RunStatus.cancelled


# --- output handling ---


def test_lines_appended_to_stdout_tail():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunOutputEvent(
        slug="s", at=_now(), step_index=0, fd="stdout", lines=["a", "b"],
    ))
    assert run.record.steps[0].stdout_tail == "a\nb\n"


def test_stderr_lines_separate_from_stdout():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunOutputEvent(
        slug="s", at=_now(), step_index=0, fd="stdout", lines=["out"],
    ))
    run.emit(RunOutputEvent(
        slug="s", at=_now(), step_index=0, fd="stderr", lines=["err"],
    ))
    step = run.record.steps[0]
    assert step.stdout_tail == "out\n"
    assert step.stderr_tail == "err\n"


def test_tail_caps_at_128k():
    run = Run(slug="s", phone_command=_pc())
    big = "x" * (OUTPUT_TAIL_CAP * 2)
    run.emit(RunOutputEvent(
        slug="s", at=_now(), step_index=0, fd="stdout", lines=[big],
    ))
    tail = run.record.steps[0].stdout_tail
    assert len(tail) == OUTPUT_TAIL_CAP


def test_dropped_counters_accumulate():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunOutputEvent(
        slug="s", at=_now(), step_index=0, fd="stdout", dropped_lines=3,
    ))
    run.emit(RunOutputEvent(
        slug="s", at=_now(), step_index=0, fd="stdout", dropped_lines=4,
    ))
    assert run.record.steps[0].stdout_dropped == 7


# --- subscriptions ---


def test_subscribers_receive_events():
    async def go() -> None:
        run = Run(slug="s", phone_command=_pc())
        q = run.subscribe()
        run.emit(RunStateRunning(slug="s", at=_now()))
        ev = await asyncio.wait_for(q.get(), timeout=0.1)
        assert isinstance(ev, RunStateRunning)
    asyncio.run(go())


def test_multiple_subscribers_all_receive():
    async def go() -> None:
        run = Run(slug="s", phone_command=_pc())
        q1, q2 = run.subscribe(), run.subscribe()
        run.emit(RunStateRunning(slug="s", at=_now()))
        e1 = await asyncio.wait_for(q1.get(), timeout=0.1)
        e2 = await asyncio.wait_for(q2.get(), timeout=0.1)
        assert isinstance(e1, RunStateRunning)
        assert isinstance(e2, RunStateRunning)
    asyncio.run(go())


def test_unsubscribe_stops_delivery():
    async def go() -> None:
        run = Run(slug="s", phone_command=_pc())
        q = run.subscribe()
        run.unsubscribe(q)
        run.emit(RunStateRunning(slug="s", at=_now()))
        assert q.empty()
    asyncio.run(go())


def test_listener_called_synchronously():
    run = Run(slug="s", phone_command=_pc())
    seen: list[str] = []
    run.add_listener(lambda ev: seen.append(ev.type))
    run.emit(RunStateCreated(slug="s", at=_now()))
    run.emit(RunStateRunning(slug="s", at=_now()))
    assert seen == ["created", "running"]


def test_listener_exception_does_not_break_emit():
    run = Run(slug="s", phone_command=_pc())

    def boom(ev):
        raise RuntimeError("listener failed")

    run.add_listener(boom)
    seen: list[str] = []
    run.add_listener(lambda ev: seen.append(ev.type))
    run.emit(RunStateRunning(slug="s", at=_now()))
    assert seen == ["running"]


def test_record_includes_transitions():
    run = Run(slug="s", phone_command=_pc())
    run.emit(RunStateCreated(slug="s", at=_now()))
    run.emit(RunStateRunning(slug="s", at=_now()))
    run.emit(RunStateCompleted(slug="s", at=_now()))
    types = [t.type for t in run.record.transitions]
    assert types == ["created", "running", "completed"]
