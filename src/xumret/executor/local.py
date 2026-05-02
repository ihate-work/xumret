"""LocalExecutor — runs PhoneCommand pipelines as subprocesses.

Used in single mode where everything runs on the phone.
"""

from __future__ import annotations

import asyncio
import uuid

import ihate_work.o11y as o11y

from xumret.executor.models import (
    DaemonProcessStatus,
    DaemonStatus,
    PhoneCommand,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
    Pipe,
    ProcessResult,
)
from xumret.server_bridge.models import (
    CancelCommand,
    CommandError,
    DaemonEnded,
    DaemonStatusReport,
    EndDaemon,
    QueryDaemon,
    QueryStatus,
    SubmitCommand,
    SubmitDaemonStarted,
    SubmitOneshotResult,
)

logger, *_ = o11y.get_o11y(__name__)


class _RunningDaemon:
    """Bookkeeping for a running daemon pipeline."""

    def __init__(
        self,
        handle_id: str,
        command_id: str,
        procs: list[asyncio.subprocess.Process],
    ):
        self.handle_id = handle_id
        self.command_id = command_id
        self.procs = procs
        self.stdout_tails: list[str] = [""] * len(procs)
        self.stderr_tails: list[str] = [""] * len(procs)


class LocalExecutor:
    """Implements Executor protocol by spawning local subprocesses."""

    def __init__(self, timeout: float = 60.0):
        self._timeout = timeout
        self._daemons: dict[str, _RunningDaemon] = {}  # handle_id -> daemon
        self._cancel_events: dict[str, asyncio.Event] = {}  # command_id -> event

    # ── Executor protocol ────────────────────────────────────────────

    async def submit(self, cmd: SubmitCommand) -> SubmitOneshotResult | SubmitDaemonStarted | CommandError:
        pc = cmd.phone_command
        try:
            if pc.daemon:
                return await self._start_daemon(cmd)
            else:
                return await self._run_oneshot(cmd)
        except Exception as e:
            logger.exception("submit failed", command_id=cmd.command_id, error=str(e))
            return CommandError(command_id=cmd.command_id, error=str(e))

    async def cancel(self, cmd: CancelCommand) -> None:
        ev = self._cancel_events.get(cmd.command_id)
        if ev:
            ev.set()
        # Also kill any daemon whose command_id matches
        for daemon in list(self._daemons.values()):
            if daemon.command_id == cmd.command_id:
                await self._kill_daemon(daemon)

    async def query_status(self, cmd: QueryStatus) -> DaemonStatusReport | CommandError:
        for daemon in self._daemons.values():
            if daemon.command_id == cmd.command_id:
                return self._build_daemon_status(daemon)
        return CommandError(command_id=cmd.command_id, error="not_found")

    async def query_daemon(self, cmd: QueryDaemon) -> DaemonStatusReport:
        daemon = self._daemons.get(cmd.handle_id)
        if not daemon:
            return DaemonStatusReport(status=DaemonStatus(
                handle_id=cmd.handle_id, steps=[], all_running=False,
            ))
        return self._build_daemon_status(daemon)

    async def end_daemon(self, cmd: EndDaemon) -> DaemonEnded:
        daemon = self._daemons.pop(cmd.handle_id, None)
        if not daemon:
            return DaemonEnded(handle_id=cmd.handle_id, final_steps=[])
        final = await self._kill_daemon(daemon)
        return DaemonEnded(handle_id=cmd.handle_id, final_steps=final)

    # ── One-shot execution ───────────────────────────────────────────

    async def _run_oneshot(self, cmd: SubmitCommand) -> SubmitOneshotResult | CommandError:
        cancel_ev = asyncio.Event()
        self._cancel_events[cmd.command_id] = cancel_ev
        try:
            procs = await self._spawn_pipeline(cmd.phone_command)
            results = await self._wait_pipeline(procs, cancel_ev)
            return SubmitOneshotResult(result=PhoneCommandResult(
                command_id=cmd.command_id, steps=results,
            ))
        except asyncio.CancelledError:
            return CommandError(command_id=cmd.command_id, error="cancelled")
        except Exception as e:
            return CommandError(command_id=cmd.command_id, error=str(e))
        finally:
            self._cancel_events.pop(cmd.command_id, None)

    # ── Daemon execution ─────────────────────────────────────────────

    async def _start_daemon(self, cmd: SubmitCommand) -> SubmitDaemonStarted:
        procs = await self._spawn_pipeline(cmd.phone_command)
        handle_id = str(uuid.uuid4())
        daemon = _RunningDaemon(
            handle_id=handle_id, command_id=cmd.command_id, procs=procs,
        )
        self._daemons[handle_id] = daemon
        logger.info("daemon started", handle_id=handle_id, command_id=cmd.command_id)
        return SubmitDaemonStarted(handle=PhoneCommandDaemonHandle(
            command_id=cmd.command_id, handle_id=handle_id,
        ))

    # ── Pipeline helpers ─────────────────────────────────────────────

    async def _spawn_pipeline(self, pc: PhoneCommand) -> list[asyncio.subprocess.Process]:
        """Spawn all steps, wiring connections between them."""
        procs: list[asyncio.subprocess.Process] = []
        prev_stdout: int | asyncio.subprocess.Process | None = None

        for i, step in enumerate(pc.steps):
            stdin_source = None
            if i > 0 and i - 1 < len(pc.connections):
                conn = pc.connections[i - 1]
                if isinstance(conn, Pipe) and procs:
                    stdin_source = procs[i - 1].stdout

            proc = await asyncio.create_subprocess_exec(
                *step.argv,
                stdin=stdin_source if stdin_source else asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            procs.append(proc)
            logger.debug("spawned step", step=i, argv=step.argv, pid=proc.pid)

        return procs

    async def _wait_pipeline(
        self,
        procs: list[asyncio.subprocess.Process],
        cancel_ev: asyncio.Event,
    ) -> list[ProcessResult]:
        """Wait for all processes in the pipeline to finish."""
        results: list[ProcessResult] = []

        async def wait_one(proc: asyncio.subprocess.Process) -> ProcessResult:
            stdout_bytes, stderr_bytes = await proc.communicate()
            return ProcessResult(
                exit_code=proc.returncode or 0,
                stdout=(stdout_bytes or b"").decode(errors="replace"),
                stderr=(stderr_bytes or b"").decode(errors="replace"),
            )

        wait_task = asyncio.gather(*[wait_one(p) for p in procs])
        cancel_task = asyncio.create_task(cancel_ev.wait())

        done, pending = await asyncio.wait(
            [wait_task, cancel_task], return_when=asyncio.FIRST_COMPLETED,
        )

        if cancel_task in done:
            wait_task.cancel()
            for p in procs:
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
            raise asyncio.CancelledError()

        cancel_task.cancel()
        results = wait_task.result()
        return results

    # ── Daemon helpers ───────────────────────────────────────────────

    def _build_daemon_status(self, daemon: _RunningDaemon) -> DaemonStatusReport:
        steps = []
        for i, proc in enumerate(daemon.procs):
            running = proc.returncode is None
            steps.append(DaemonProcessStatus(
                running=running,
                exit_code=proc.returncode,
                stdout_tail=daemon.stdout_tails[i],
                stderr_tail=daemon.stderr_tails[i],
            ))
        return DaemonStatusReport(status=DaemonStatus(
            handle_id=daemon.handle_id,
            steps=steps,
            all_running=all(s.running for s in steps),
        ))

    async def _kill_daemon(self, daemon: _RunningDaemon) -> list[ProcessResult]:
        results: list[ProcessResult] = []
        for proc in daemon.procs:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        # Give processes a moment to exit, then force-kill
        await asyncio.sleep(0.5)
        for proc in daemon.procs:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            stdout_bytes, stderr_bytes = await proc.communicate()
            results.append(ProcessResult(
                exit_code=proc.returncode or -1,
                stdout=(stdout_bytes or b"").decode(errors="replace"),
                stderr=(stderr_bytes or b"").decode(errors="replace"),
            ))
        return results
