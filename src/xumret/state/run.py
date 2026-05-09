"""Run — live, subscribable handle for one execution.

A Run is, all at once:

- the receipt (slug, phone_command, current status)
- the producer (executor calls `.emit(event)` as work proceeds)
- the subscription point (multiple consumers attach to the same stream)

Internal state mutates as events are applied; subscribers read events from
their own queue and reconstruct state event-sourcing-style. The `record`
property returns a current materialized snapshot for slim-record reads.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import ihate_work.o11y as o11y

from xumret.executor.models import PhoneCommand
from xumret.state.models import (
    TERMINAL_STATUSES,
    RunEvent,
    RunOutputEvent,
    RunRecord,
    RunStateCancelled,
    RunStateCompleted,
    RunStateCreated,
    RunStateDaemonEnded,
    RunStateDaemonStarted,
    RunStateEvent,
    RunStateFailed,
    RunStateRunning,
    RunStateStepExited,
    RunStateStepStarted,
    RunStatus,
    StepState,
)

logger, *_ = o11y.get_o11y(__name__)

OUTPUT_TAIL_CAP = 128 * 1024  # 128 KiB per process per fd


class Run:
    """Live per-run handle: receipt + producer + multi-subscriber stream."""

    def __init__(self, *, slug: str, phone_command: PhoneCommand) -> None:
        self.slug = slug
        self.phone_command = phone_command
        self.created_at = time.time()
        self._status = RunStatus.pending
        self._error: str | None = None
        self._updated_at = self.created_at
        self._steps = [StepState() for _ in phone_command.steps]
        self._transitions: list[RunStateEvent] = []
        self._daemon_started = False
        self._daemon_ended = False
        self._subscribers: list[asyncio.Queue[RunEvent]] = []
        self._listeners: list[Callable[[RunEvent], None]] = []

    # --- queries ---

    @property
    def status(self) -> RunStatus:
        return self._status

    @property
    def is_terminal(self) -> bool:
        return self._status in TERMINAL_STATUSES

    @property
    def is_live(self) -> bool:
        return not self.is_terminal

    @property
    def record(self) -> RunRecord:
        return RunRecord(
            slug=self.slug,
            phone_command=self.phone_command,
            status=self._status,
            created_at=self.created_at,
            updated_at=self._updated_at,
            error=self._error,
            daemon_started=self._daemon_started,
            daemon_ended=self._daemon_ended,
            steps=[s.model_copy() for s in self._steps],
            transitions=list(self._transitions),
        )

    # --- producer ---

    def emit(self, event: RunEvent) -> None:
        """Apply event to internal state, notify listeners, broadcast to subscribers."""
        self._apply(event)
        for fn in list(self._listeners):
            try:
                fn(event)
            except Exception:
                logger.exception("run listener failed", slug=self.slug)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Slow consumer: drop oldest, push new.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    # --- subscriptions ---

    def subscribe(self) -> asyncio.Queue[RunEvent]:
        q: asyncio.Queue[RunEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[RunEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def add_listener(self, fn: Callable[[RunEvent], None]) -> None:
        """Register a sync callback invoked during emit (before queue fan-out)."""
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[RunEvent], None]) -> None:
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    # --- internal: event application ---

    def _apply(self, event: RunEvent) -> None:
        self._updated_at = event.at
        if isinstance(event, RunOutputEvent):
            self._apply_output(event)
            return

        # state event
        self._transitions.append(event)
        if isinstance(event, RunStateCreated):
            self._status = RunStatus.pending
        elif isinstance(event, RunStateRunning):
            self._status = RunStatus.running
        elif isinstance(event, RunStateStepStarted):
            self._steps[event.step_index].pid = event.pid
        elif isinstance(event, RunStateStepExited):
            self._steps[event.step_index].exit_code = event.exit_code
        elif isinstance(event, RunStateCompleted):
            self._status = RunStatus.completed
        elif isinstance(event, RunStateFailed):
            self._status = RunStatus.failed
            self._error = event.error
        elif isinstance(event, RunStateCancelled):
            self._status = RunStatus.cancelled
        elif isinstance(event, RunStateDaemonStarted):
            self._daemon_started = True
        elif isinstance(event, RunStateDaemonEnded):
            self._daemon_ended = True
        # daemon_status: no state mutation, just flows through

    def _apply_output(self, event: RunOutputEvent) -> None:
        step = self._steps[event.step_index]
        if event.fd == "stdout":
            tail = step.stdout_tail
            dropped = step.stdout_dropped
        else:
            tail = step.stderr_tail
            dropped = step.stderr_dropped

        if event.lines:
            tail = (tail + "\n".join(event.lines) + "\n")[-OUTPUT_TAIL_CAP:]
        # binary-mode bytes are not appended to the snapshot tail (it's a text
        # field). Live consumers see the bytes via the SSE event itself.

        if event.dropped_lines:
            dropped += event.dropped_lines
        if event.dropped_bytes:
            dropped += event.dropped_bytes

        if event.fd == "stdout":
            step.stdout_tail = tail
            step.stdout_dropped = dropped
        else:
            step.stderr_tail = tail
            step.stderr_dropped = dropped
