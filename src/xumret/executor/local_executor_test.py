from __future__ import annotations

import asyncio
import base64

from xumret.executor.local_executor import LocalExecutor
from xumret.executor.models import (
    CommandStep,
    PhoneCommand,
    RunOption,
    StreamConfig,
)
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateFailed,
    RunStateStepExited,
    RunStateStepStarted,
    RunStateTimedOut,
    RunStatus,
)
from xumret.state.run import Run


def _run(steps: list[CommandStep], *, timeout: float | None = None) -> Run:
    pc = PhoneCommand(
        name="t",
        steps=steps,
        run_option=RunOption(timeout=timeout),
    )
    return Run(slug="s", phone_command=pc)


def test_oneshot_echo_completes() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([
            CommandStep(
                argv=["sh", "-c", "echo hello"],
                stdout_stream=StreamConfig(capture=True),
            ),
        ])
        await ex.run(run)
        assert run.status == RunStatus.completed
        assert run.record.steps[0].exit_code == 0
        assert run.record.steps[0].stdout_tail == "hello\n"
    asyncio.run(go())


def test_step_events_emitted_in_order() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([CommandStep(argv=["sh", "-c", "echo a"])])
        q = run.subscribe()
        await ex.run(run)
        kinds: list[type] = []
        while not q.empty():
            kinds.append(type(q.get_nowait()))
        assert kinds.index(RunStateStepStarted) < kinds.index(RunStateStepExited)
        assert kinds[-1] is RunStateCompleted
    asyncio.run(go())


def test_nonzero_exit_emits_failed() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([CommandStep(argv=["sh", "-c", "exit 7"])])
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
            CommandStep(
                argv=["sh", "-c", "echo oops 1>&2; exit 0"],
                stderr_stream=StreamConfig(capture=True),
            ),
        ])
        await ex.run(run)
        assert "oops" in run.record.steps[0].stderr_tail
    asyncio.run(go())


def test_dropped_stream_produces_no_tail() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        # Default StreamConfig: not captured, not forwarded → dropped.
        run = _run([CommandStep(argv=["sh", "-c", "echo dropped"])])
        await ex.run(run)
        assert run.status == RunStatus.completed
        assert run.record.steps[0].stdout_tail == ""
    asyncio.run(go())


def test_forward_routes_stdout_to_next_stdin() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([
            CommandStep(
                argv=["sh", "-c", "echo hello"],
                stdout_stream=StreamConfig(forward_dest_process_idx=1),
            ),
            CommandStep(
                argv=["tr", "a-z", "A-Z"],
                stdout_stream=StreamConfig(capture=True),
            ),
        ])
        await ex.run(run)
        assert run.status == RunStatus.completed
        assert run.record.steps[1].stdout_tail == "HELLO\n"
        # Step 0 stdout was forwarded only — not captured, no tail.
        assert run.record.steps[0].stdout_tail == ""
    asyncio.run(go())


def test_forward_and_capture_tees_to_both() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([
            CommandStep(
                argv=["sh", "-c", "echo hello"],
                stdout_stream=StreamConfig(capture=True, forward_dest_process_idx=1),
            ),
            CommandStep(
                argv=["tr", "a-z", "A-Z"],
                stdout_stream=StreamConfig(capture=True),
            ),
        ])
        await ex.run(run)
        assert run.status == RunStatus.completed
        assert run.record.steps[0].stdout_tail == "hello\n"
        assert run.record.steps[1].stdout_tail == "HELLO\n"
    asyncio.run(go())


def test_cancel_kills_long_running_proc() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([CommandStep(argv=["sh", "-c", "sleep 30"])])
        task = asyncio.create_task(ex.run(run))
        await asyncio.sleep(0.05)
        await ex.stop("s")
        await asyncio.wait_for(task, timeout=2.0)
        assert run.status == RunStatus.cancelled
        last = run.record.transitions[-1]
        assert isinstance(last, RunStateCancelled)
    asyncio.run(go())


def test_timeout_emits_timed_out() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([CommandStep(argv=["sh", "-c", "sleep 30"])], timeout=0.1)
        await ex.run(run)
        assert run.status == RunStatus.timed_out
        last = run.record.transitions[-1]
        assert isinstance(last, RunStateTimedOut)
    asyncio.run(go())


def test_binary_mode_emits_base64() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([
            CommandStep(
                argv=[
                    "python3", "-c",
                    "import sys;sys.stdout.buffer.write(b'\\x00\\xff\\xab')",
                ],
                stdout_stream=StreamConfig(mode="binary", capture=True),
            ),
        ])
        q = run.subscribe()
        await ex.run(run)
        decoded = b""
        while not q.empty():
            ev = q.get_nowait()
            if isinstance(ev, RunOutputEvent) and ev.fd == "stdout" and ev.bytes:
                decoded += base64.b64decode(ev.bytes)
        assert decoded == b"\x00\xff\xab"
        assert run.status == RunStatus.completed
    asyncio.run(go())


def test_capture_writes_to_per_run_temp_file() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([
            CommandStep(
                argv=["sh", "-c", "echo hello"],
                stdout_stream=StreamConfig(capture=True),
            ),
        ])
        await ex.run(run)
        tmpdir = ex.tmpdir_for("s")
        assert tmpdir is not None
        assert (tmpdir / "step0.stdout").read_bytes() == b"hello\n"
    asyncio.run(go())


def test_shutdown_kills_running_procs() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([CommandStep(argv=["sh", "-c", "sleep 30"])])
        task = asyncio.create_task(ex.run(run))
        await asyncio.sleep(0.05)
        await ex.shutdown()
        await asyncio.wait_for(task, timeout=2.0)
        assert run.is_terminal
    asyncio.run(go())


def test_spawn_failure_emits_failed() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        run = _run([CommandStep(argv=["this-binary-does-not-exist-xyz123"])])
        await ex.run(run)
        assert run.status == RunStatus.failed
    asyncio.run(go())


def test_invalid_graph_emits_failed() -> None:
    async def go() -> None:
        ex = LocalExecutor()
        # Forward to a non-existent step → builder rejects → run fails.
        run = _run([
            CommandStep(
                argv=["echo", "hi"],
                stdout_stream=StreamConfig(forward_dest_process_idx=5),
            ),
        ])
        await ex.run(run)
        assert run.status == RunStatus.failed
    asyncio.run(go())
