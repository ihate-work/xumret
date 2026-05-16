from __future__ import annotations

import asyncio
import base64

from xumret.executor.local_executor import LocalExecutor
from xumret.executor.models import (
    PhoneCommand,
    Pipe,
    ProcessStep,
    StreamConfig,
)
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateFailed,
    RunStateStepExited,
    RunStateStepStarted,
    RunStatus,
)
from xumret.state.run import Run


def _run(steps: list[ProcessStep], *, connections=None, daemon: bool = False) -> Run:
    pc = PhoneCommand(
        name="t",
        steps=steps,
        connections=connections or [],
        daemon=daemon,
    )
    return Run(slug="s", phone_command=pc)


def test_oneshot_echo_completes() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["sh", "-c", "echo hello"])])
        await ex.run(run)
        assert run.status == RunStatus.completed
        assert run.record.steps[0].exit_code == 0
        assert run.record.steps[0].stdout_tail == "hello\n"
    asyncio.run(go())


def test_step_events_emitted_in_order() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["sh", "-c", "echo a"])])
        q = run.subscribe()
        await ex.run(run)
        kinds: list[type] = []
        while not q.empty():
            kinds.append(type(q.get_nowait()))
        # step_started must precede step_exited
        assert kinds.index(RunStateStepStarted) < kinds.index(RunStateStepExited)
        # completed last
        assert kinds[-1] is RunStateCompleted
    asyncio.run(go())


def test_nonzero_exit_emits_failed() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["sh", "-c", "exit 7"])])
        await ex.run(run)
        assert run.status == RunStatus.failed
        assert run.record.steps[0].exit_code == 7
        last = run.record.transitions[-1]
        assert isinstance(last, RunStateFailed)
    asyncio.run(go())


def test_stderr_captured_per_step() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([
            ProcessStep(argv=["sh", "-c", "echo oops 1>&2; exit 0"]),
        ])
        await ex.run(run)
        assert "oops" in run.record.steps[0].stderr_tail
    asyncio.run(go())


def test_pipe_pipeline_routes_stdout_to_next_stdin() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run(
            steps=[
                ProcessStep(argv=["sh", "-c", "echo hello"]),
                ProcessStep(argv=["tr", "a-z", "A-Z"]),
            ],
            connections=[Pipe()],
        )
        await ex.run(run)
        assert run.status == RunStatus.completed
        # Terminal step's stdout_tail captures the uppercased output
        assert run.record.steps[1].stdout_tail == "HELLO\n"
        # First step's stdout went down the pipe — not captured here
        assert run.record.steps[0].stdout_tail == ""
    asyncio.run(go())


def test_cancel_kills_long_running_proc() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["sh", "-c", "sleep 30"])])
        task = asyncio.create_task(ex.run(run))
        await asyncio.sleep(0.05)
        await ex.stop("s")
        await asyncio.wait_for(task, timeout=2.0)
        assert run.status == RunStatus.cancelled
        last = run.record.transitions[-1]
        assert isinstance(last, RunStateCancelled)
    asyncio.run(go())


def test_daemon_emits_started_and_ends_on_stop() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["sh", "-c", "sleep 30"])], daemon=True)
        task = asyncio.create_task(ex.run(run))
        await asyncio.sleep(0.05)
        types = [t.type for t in run.record.transitions]
        assert "daemon_started" in types
        assert run.is_live
        await ex.stop("s")
        await asyncio.wait_for(task, timeout=2.0)
        assert run.status == RunStatus.cancelled
        types = [t.type for t in run.record.transitions]
        assert "daemon_ended" in types
        assert types[-1] == "cancelled"
    asyncio.run(go())


def test_binary_mode_emits_base64() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        # Print a few bytes that include 0x00 and 0xff
        run = _run([
            ProcessStep(
                argv=["python3", "-c", "import sys;sys.stdout.buffer.write(b'\\x00\\xff\\xab')"],
                stdout_stream=StreamConfig(mode="binary"),
            ),
        ])
        q = run.subscribe()
        await ex.run(run)
        # Find the binary output event
        decoded = b""
        while not q.empty():
            ev = q.get_nowait()
            if isinstance(ev, RunOutputEvent) and ev.fd == "stdout" and ev.bytes:
                decoded += base64.b64decode(ev.bytes)
        assert decoded == b"\x00\xff\xab"
        assert run.status == RunStatus.completed
    asyncio.run(go())


def test_shutdown_kills_running_procs() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["sh", "-c", "sleep 30"])])
        task = asyncio.create_task(ex.run(run))
        await asyncio.sleep(0.05)
        await ex.shutdown()
        await asyncio.wait_for(task, timeout=2.0)
        assert run.is_terminal
    asyncio.run(go())


def test_spawn_failure_emits_failed() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([ProcessStep(argv=["this-binary-does-not-exist-xyz123"])])
        await ex.run(run)
        assert run.status == RunStatus.failed
    asyncio.run(go())
