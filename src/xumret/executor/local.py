"""LocalExecutor — runs PhoneCommand pipelines as subprocesses.

Single mode: everything runs on this machine. Each `run()` call drives one
`Run`, emitting `RunStateEvent`s for lifecycle and `RunOutputEvent`s for
incremental stdout/stderr. No return values — the Run is the observation point.
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from typing import Literal

import ihate_work.o11y as o11y

from xumret.executor.models import (
    PhoneCommand,
    Pipe,
    StreamConfig,
)
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateDaemonEnded,
    RunStateDaemonStarted,
    RunStateFailed,
    RunStateRunning,
    RunStateStepExited,
    RunStateStepStarted,
)
from xumret.state.run import Run

logger, *_ = o11y.get_o11y(__name__)

_BINARY_CHUNK = 4096
_KILL_GRACE_SEC = 0.5


class LocalExecutor:
    """Implements `Executor` by spawning local subprocesses."""

    def __init__(self) -> None:
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._procs: dict[str, list[asyncio.subprocess.Process]] = {}

    # ── Executor protocol ────────────────────────────────────────────

    async def run(self, run: Run) -> None:
        slug = run.slug
        cancel_ev = asyncio.Event()
        self._cancel_events[slug] = cancel_ev
        try:
            await self._drive(run, cancel_ev)
        finally:
            self._cancel_events.pop(slug, None)
            self._procs.pop(slug, None)

    async def stop(self, slug: str) -> None:
        ev = self._cancel_events.get(slug)
        if ev is not None:
            ev.set()

    async def shutdown(self) -> None:
        for ev in list(self._cancel_events.values()):
            ev.set()
        # Best-effort kill in case a run is mid-spawn and didn't observe the event.
        for procs in list(self._procs.values()):
            for p in procs:
                try:
                    p.kill()
                except ProcessLookupError:
                    pass

    # ── Run driver ──────────────────────────────────────────────────

    async def _drive(self, run: Run, cancel_ev: asyncio.Event) -> None:
        slug = run.slug
        pc = run.phone_command
        run.emit(RunStateRunning(slug=slug, at=time.time()))

        try:
            procs = await self._spawn_pipeline(pc)
        except Exception as e:
            logger.exception("spawn failed", slug=slug)
            run.emit(RunStateFailed(slug=slug, at=time.time(), error=str(e)))
            return

        self._procs[slug] = procs

        for i, proc in enumerate(procs):
            run.emit(RunStateStepStarted(
                slug=slug, at=time.time(), step_index=i, pid=proc.pid or 0,
            ))

        is_daemon = pc.daemon
        if is_daemon:
            run.emit(RunStateDaemonStarted(slug=slug, at=time.time()))

        # Reader tasks: one per captured fd, honoring StreamConfig.
        reader_tasks: list[asyncio.Task] = []
        for i, (proc, step) in enumerate(zip(procs, pc.steps, strict=False)):
            if proc.stdout is not None:
                reader_tasks.append(asyncio.create_task(
                    self._read_fd(
                        run, i, "stdout", proc.stdout, step.stdout_stream,
                    ),
                    name=f"reader[{slug}.{i}.stdout]",
                ))
            if proc.stderr is not None:
                reader_tasks.append(asyncio.create_task(
                    self._read_fd(
                        run, i, "stderr", proc.stderr, step.stderr_stream,
                    ),
                    name=f"reader[{slug}.{i}.stderr]",
                ))

        # Wait task: emits step_exited as each proc finishes.
        async def _wait_step(idx: int, p: asyncio.subprocess.Process) -> None:
            exit_code = await p.wait()
            run.emit(RunStateStepExited(
                slug=slug, at=time.time(), step_index=idx, exit_code=exit_code,
            ))

        async def _wait_all() -> None:
            await asyncio.gather(*[_wait_step(i, p) for i, p in enumerate(procs)])

        wait_task = asyncio.create_task(_wait_all(), name=f"wait[{slug}]")
        cancel_task = asyncio.create_task(cancel_ev.wait(), name=f"cancel[{slug}]")

        done, _pending = await asyncio.wait(
            [wait_task, cancel_task], return_when=asyncio.FIRST_COMPLETED,
        )

        cancelled = cancel_task in done

        if cancelled:
            for p in procs:
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
        else:
            cancel_task.cancel()

        # Drain wait_task and reader_tasks regardless — kills cause proc.wait
        # to return, which lets readers EOF.
        try:
            await wait_task
        except asyncio.CancelledError:
            pass
        await asyncio.gather(*reader_tasks, return_exceptions=True)

        if is_daemon:
            run.emit(RunStateDaemonEnded(slug=slug, at=time.time()))

        if cancelled:
            run.emit(RunStateCancelled(slug=slug, at=time.time()))
            return

        nonzero = [p.returncode for p in procs if p.returncode not in (0, None)]
        if nonzero:
            run.emit(RunStateFailed(
                slug=slug, at=time.time(),
                error=f"non-zero exit: {nonzero}",
            ))
        else:
            run.emit(RunStateCompleted(slug=slug, at=time.time()))

    # ── Pipeline spawn ──────────────────────────────────────────────

    async def _spawn_pipeline(
        self, pc: PhoneCommand,
    ) -> list[asyncio.subprocess.Process]:
        """Spawn all steps, wiring connections between them."""
        procs: list[asyncio.subprocess.Process] = []
        fds_to_close: list[int] = []

        for i, step in enumerate(pc.steps):
            stdin_arg: int | None = None
            if i > 0 and i - 1 < len(pc.connections):
                conn = pc.connections[i - 1]
                if isinstance(conn, Pipe):
                    stdin_arg = fds_to_close[-1]

            stdout_arg: int | None = None
            if i < len(pc.connections) and isinstance(pc.connections[i], Pipe):
                read_fd, write_fd = os.pipe()
                stdout_arg = write_fd
                fds_to_close.append(read_fd)

            proc = await asyncio.create_subprocess_exec(
                *step.argv,
                stdin=stdin_arg,
                stdout=stdout_arg if stdout_arg is not None else asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            procs.append(proc)
            logger.debug("spawned step", step=i, argv=step.argv, pid=proc.pid)

            if stdin_arg is not None:
                os.close(stdin_arg)
                fds_to_close.remove(stdin_arg)
            if stdout_arg is not None:
                os.close(stdout_arg)

        return procs

    # ── Per-fd readers ──────────────────────────────────────────────

    async def _read_fd(
        self,
        run: Run,
        step_index: int,
        fd_name: Literal["stdout", "stderr"],
        reader: asyncio.StreamReader,
        cfg: StreamConfig,
    ) -> None:
        # back_pressure: TODO honor by gating reads on subscriber queue depth.
        # v0.2 always drains; per-subscriber drop accounting is in Run.emit.
        try:
            if cfg.mode == "lines":
                await self._read_lines(run, step_index, fd_name, reader)
            else:
                await self._read_binary(run, step_index, fd_name, reader)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "reader crashed", slug=run.slug, step=step_index, fd=fd_name,
            )

    async def _read_lines(
        self,
        run: Run,
        step_index: int,
        fd_name: Literal["stdout", "stderr"],
        reader: asyncio.StreamReader,
    ) -> None:
        while True:
            line = await reader.readline()
            if not line:
                return
            decoded = line.decode("utf-8", errors="replace")
            # drop the trailing \n; preserve any \r in the content
            if decoded.endswith("\n"):
                decoded = decoded[:-1]
            run.emit(RunOutputEvent(
                slug=run.slug, at=time.time(), step_index=step_index,
                fd=fd_name, lines=[decoded],
            ))

    async def _read_binary(
        self,
        run: Run,
        step_index: int,
        fd_name: Literal["stdout", "stderr"],
        reader: asyncio.StreamReader,
    ) -> None:
        while True:
            chunk = await reader.read(_BINARY_CHUNK)
            if not chunk:
                return
            b64 = base64.b64encode(chunk).decode("ascii")
            run.emit(RunOutputEvent(
                slug=run.slug, at=time.time(), step_index=step_index,
                fd=fd_name, bytes=b64,
            ))
