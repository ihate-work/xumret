"""LocalExecutor — runs PhoneCommand pipelines as subprocesses.

Single mode: everything runs on this machine. Each `run()` call drives one
`Run`, emitting `RunStateEvent`s for lifecycle and `RunOutputEvent`s for
captured stdout/stderr. Captured streams are written through to per-run
temp files; forwarded streams are piped step→step through the executor.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import time
from pathlib import Path
from typing import BinaryIO, Literal

import ihate_work.o11y as o11y

from xumret.executor.process_graph import (
    FdPlan,
    GraphValidationError,
    ProcessGraph,
    ProcessGraphBuilder,
)
from xumret.state.models import (
    RunOutputEvent,
    RunStateCancelled,
    RunStateCompleted,
    RunStateFailed,
    RunStateRunning,
    RunStateStepExited,
    RunStateStepStarted,
    RunStateTimedOut,
)
from xumret.state.run import Run

logger, *_ = o11y.get_o11y(__name__)

_BINARY_CHUNK = 4096
_TERM_GRACE_SEC = 0.5

FdName = Literal["stdout", "stderr"]
_Outcome = Literal["completed", "cancelled", "timed_out"]


class LocalExecutor:
    """Implements `Executor` by spawning local subprocesses."""

    def __init__(self) -> None:
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._procs: dict[str, list[asyncio.subprocess.Process]] = {}
        self._tmpdirs: dict[str, Path] = {}
        self._builder = ProcessGraphBuilder()

    # ── Executor protocol ────────────────────────────────────────────

    async def run(self, run: Run) -> None:
        slug = run.slug
        cancel_ev = asyncio.Event()
        self._cancel_events[slug] = cancel_ev
        tmpdir = Path(tempfile.mkdtemp(prefix=f"xumret-run-{slug}-"))
        self._tmpdirs[slug] = tmpdir
        try:
            await self._drive(run, cancel_ev, tmpdir)
        finally:
            self._cancel_events.pop(slug, None)
            self._procs.pop(slug, None)
            # _tmpdirs entry kept so callers can read captured streams after
            # the run terminates; entry and directory both leak until shutdown
            # or an explicit cleanup (deferred).

    async def stop(self, slug: str) -> None:
        ev = self._cancel_events.get(slug)
        if ev is not None:
            ev.set()

    async def shutdown(self) -> None:
        for ev in list(self._cancel_events.values()):
            ev.set()
        for procs in list(self._procs.values()):
            for p in procs:
                try:
                    p.kill()
                except ProcessLookupError:
                    pass

    def tmpdir_for(self, slug: str) -> Path | None:
        return self._tmpdirs.get(slug)

    # ── Driver ───────────────────────────────────────────────────────

    async def _drive(self, run: Run, cancel_ev: asyncio.Event, tmpdir: Path) -> None:
        slug = run.slug
        try:
            graph = self._builder.build(run.phone_command)
        except GraphValidationError as e:
            run.emit(RunStateFailed(slug=slug, at=time.time(), error=str(e)))
            return

        run.emit(RunStateRunning(slug=slug, at=time.time()))

        try:
            procs, fwd_fds = await self._spawn(graph)
        except Exception as e:
            logger.exception("spawn failed", slug=slug)
            run.emit(RunStateFailed(slug=slug, at=time.time(), error=str(e)))
            return

        self._procs[slug] = procs

        for i, proc in enumerate(procs):
            run.emit(
                RunStateStepStarted(
                    slug=slug, at=time.time(), step_index=i, pid=proc.pid or 0,
                )
            )

        reader_tasks = self._start_readers(run, graph, procs, tmpdir, fwd_fds)

        async def _wait_step(idx: int, p: asyncio.subprocess.Process) -> None:
            code = await p.wait()
            run.emit(
                RunStateStepExited(
                    slug=slug, at=time.time(), step_index=idx, exit_code=code,
                )
            )

        async def _wait_all() -> None:
            await asyncio.gather(*[_wait_step(i, p) for i, p in enumerate(procs)])

        wait_task = asyncio.create_task(_wait_all(), name=f"wait[{slug}]")
        cancel_task = asyncio.create_task(cancel_ev.wait(), name=f"cancel[{slug}]")

        outcome = await self._await_outcome(wait_task, cancel_task, graph.timeout)

        if outcome in ("cancelled", "timed_out"):
            await self._terminate_gracefully(procs)
        else:
            cancel_task.cancel()

        try:
            await wait_task
        except asyncio.CancelledError:
            pass
        await asyncio.gather(*reader_tasks, return_exceptions=True)

        self._emit_terminal(run, procs, outcome)

    async def _await_outcome(
        self,
        wait_task: asyncio.Task,
        cancel_task: asyncio.Task,
        timeout: float | None,
    ) -> _Outcome:
        done, _pending = await asyncio.wait(
            [wait_task, cancel_task],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            return "timed_out"
        if cancel_task in done:
            return "cancelled"
        return "completed"

    async def _terminate_gracefully(
        self, procs: list[asyncio.subprocess.Process]
    ) -> None:
        for p in procs:
            if p.returncode is None:
                try:
                    p.terminate()
                except ProcessLookupError:
                    pass
        try:
            await asyncio.wait_for(
                asyncio.gather(*[p.wait() for p in procs], return_exceptions=True),
                timeout=_TERM_GRACE_SEC,
            )
        except asyncio.TimeoutError:
            for p in procs:
                if p.returncode is None:
                    try:
                        p.kill()
                    except ProcessLookupError:
                        pass

    def _emit_terminal(
        self,
        run: Run,
        procs: list[asyncio.subprocess.Process],
        outcome: _Outcome,
    ) -> None:
        slug = run.slug
        now = time.time()
        if outcome == "cancelled":
            run.emit(RunStateCancelled(slug=slug, at=now))
            return
        if outcome == "timed_out":
            run.emit(RunStateTimedOut(slug=slug, at=now))
            return
        nonzero = [p.returncode for p in procs if p.returncode not in (0, None)]
        if nonzero:
            run.emit(
                RunStateFailed(slug=slug, at=now, error=f"non-zero exit: {nonzero}")
            )
        else:
            run.emit(RunStateCompleted(slug=slug, at=now))

    # ── Spawn ────────────────────────────────────────────────────────

    async def _spawn(
        self, graph: ProcessGraph
    ) -> tuple[
        list[asyncio.subprocess.Process],
        dict[tuple[int, FdName], int],
    ]:
        """Spawn all steps; return procs and the forward-write fds the readers own."""
        # For each forwarding edge, create an os.pipe(): dst inherits the read
        # end as stdin; the executor (a reader task) writes to the write end.
        inbound_read_fd: dict[int, int] = {}
        outbound_write_fd: dict[tuple[int, FdName], int] = {}
        for step in graph.steps:
            fds: list[tuple[FdName, FdPlan]] = [
                ("stdout", step.stdout),
                ("stderr", step.stderr),
            ]
            for fd_name, plan in fds:
                if plan.forward_to is not None:
                    r, w = os.pipe()
                    inbound_read_fd[plan.forward_to] = r
                    outbound_write_fd[(step.step_index, fd_name)] = w

        procs: list[asyncio.subprocess.Process] = []
        try:
            for step in graph.steps:
                stdin_fd = inbound_read_fd.get(step.step_index)
                proc = await asyncio.create_subprocess_exec(
                    *step.argv,
                    stdin=stdin_fd if stdin_fd is not None else asyncio.subprocess.DEVNULL,
                    stdout=self._spawn_arg(step.stdout),
                    stderr=self._spawn_arg(step.stderr),
                )
                procs.append(proc)
                if stdin_fd is not None:
                    os.close(stdin_fd)
                logger.debug(
                    "spawned step", step=step.step_index, argv=step.argv, pid=proc.pid
                )
        except Exception:
            for fd in outbound_write_fd.values():
                _safe_close(fd)
            # Any inbound read fds we haven't yet handed off are also leaked
            # by us; close them.
            spawned_indices = {i for i in range(len(procs))}
            for dst_idx, fd in inbound_read_fd.items():
                if dst_idx not in spawned_indices:
                    _safe_close(fd)
            raise
        return procs, outbound_write_fd

    @staticmethod
    def _spawn_arg(plan: FdPlan) -> int:
        if plan.forward_to is not None or plan.capture:
            return asyncio.subprocess.PIPE
        return asyncio.subprocess.DEVNULL

    # ── Readers ──────────────────────────────────────────────────────

    def _start_readers(
        self,
        run: Run,
        graph: ProcessGraph,
        procs: list[asyncio.subprocess.Process],
        tmpdir: Path,
        fwd_fds: dict[tuple[int, FdName], int],
    ) -> list[asyncio.Task]:
        tasks: list[asyncio.Task] = []
        for step, proc in zip(graph.steps, procs, strict=True):
            fds: list[tuple[FdName, FdPlan, asyncio.StreamReader | None]] = [
                ("stdout", step.stdout, proc.stdout),
                ("stderr", step.stderr, proc.stderr),
            ]
            for fd_name, plan, reader in fds:
                if reader is None:
                    continue
                fwd_fd = fwd_fds.get((step.step_index, fd_name))
                tasks.append(
                    asyncio.create_task(
                        self._read_fd(
                            run, step.step_index, fd_name, reader, plan, tmpdir, fwd_fd,
                        ),
                        name=f"reader[{run.slug}.{step.step_index}.{fd_name}]",
                    )
                )
        return tasks

    async def _read_fd(
        self,
        run: Run,
        step_index: int,
        fd_name: FdName,
        reader: asyncio.StreamReader,
        plan: FdPlan,
        tmpdir: Path,
        fwd_fd: int | None,
    ) -> None:
        capture_f: BinaryIO | None = None
        if plan.capture:
            capture_f = (tmpdir / f"step{step_index}.{fd_name}").open("wb")
        try:
            if plan.mode == "lines":
                await self._read_lines(
                    run, step_index, fd_name, reader, plan, capture_f, fwd_fd,
                )
            else:
                await self._read_binary(
                    run, step_index, fd_name, reader, plan, capture_f, fwd_fd,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "reader crashed", slug=run.slug, step=step_index, fd=fd_name,
            )
        finally:
            if capture_f is not None:
                capture_f.close()
            if fwd_fd is not None:
                _safe_close(fwd_fd)

    async def _read_lines(
        self,
        run: Run,
        step_index: int,
        fd_name: FdName,
        reader: asyncio.StreamReader,
        plan: FdPlan,
        capture_f: BinaryIO | None,
        fwd_fd: int | None,
    ) -> None:
        loop = asyncio.get_running_loop()
        while True:
            line = await reader.readline()
            if not line:
                return
            if capture_f is not None:
                capture_f.write(line)
            if fwd_fd is not None:
                await loop.run_in_executor(None, os.write, fwd_fd, line)
            if plan.capture:
                decoded = line.decode("utf-8", errors="replace")
                if decoded.endswith("\n"):
                    decoded = decoded[:-1]
                run.emit(
                    RunOutputEvent(
                        slug=run.slug,
                        at=time.time(),
                        step_index=step_index,
                        fd=fd_name,
                        lines=[decoded],
                    )
                )

    async def _read_binary(
        self,
        run: Run,
        step_index: int,
        fd_name: FdName,
        reader: asyncio.StreamReader,
        plan: FdPlan,
        capture_f: BinaryIO | None,
        fwd_fd: int | None,
    ) -> None:
        loop = asyncio.get_running_loop()
        while True:
            chunk = await reader.read(_BINARY_CHUNK)
            if not chunk:
                return
            if capture_f is not None:
                capture_f.write(chunk)
            if fwd_fd is not None:
                await loop.run_in_executor(None, os.write, fwd_fd, chunk)
            if plan.capture:
                b64 = base64.b64encode(chunk).decode("ascii")
                run.emit(
                    RunOutputEvent(
                        slug=run.slug,
                        at=time.time(),
                        step_index=step_index,
                        fd=fd_name,
                        bytes=b64,
                    )
                )


def _safe_close(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass
