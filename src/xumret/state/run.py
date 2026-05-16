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
    RunStateEvent,
    RunStateFailed,
    RunStateRunning,
    RunStateStepExited,
    RunStateStepStarted,
    RunStateTimedOut,
    RunStatus,
    StepState,
)

logger, *_ = o11y.get_o11y(__name__)

OUTPUT_TAIL_CAP = 128 * 1024  # 128 KiB per process per fd


class Run:
    """Live per-run handle: receipt + producer + multi-subscriber stream."""

    def __init__(
        self,
        *,
        slug: str,
        phone_command: PhoneCommand,
        on_event: Callable[[RunEvent], None] | None = None,
    ) -> None:
        self.slug = slug
        self.phone_command = phone_command
        self.created_at = time.time()
        self._status = RunStatus.pending
        self._error: str | None = None
        self._updated_at = self.created_at
        self._steps = [StepState() for _ in phone_command.steps]
        self._transitions: list[RunStateEvent] = []
        self._subscribers: list[asyncio.Queue[RunEvent]] = []
        # Single sync callback fired after _apply, before subscriber fan-out.
        # Used by PhoneState for phone-wide event broadcast.
        self._on_event = on_event

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
            steps=[s.model_copy() for s in self._steps],
            transitions=list(self._transitions),
        )

    # --- producer ---

    def emit(self, event: RunEvent) -> None:
        """Apply event to internal state, invoke on_event, broadcast to subscribers."""
        self._apply(event)
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception:
                logger.exception("run on_event failed", slug=self.slug)
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

    # --- internal: event application ---

    def _apply(self, event: RunEvent) -> None:
        self._updated_at = event.at
        if isinstance(event, RunOutputEvent):
            self._apply_output(event)
            return

        self._transitions.append(event)
        if isinstance(event, RunStateRunning):
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
        elif isinstance(event, RunStateTimedOut):
            self._status = RunStatus.timed_out
        # RunStateCreated: no-op (status is already pending at construction).

    def _apply_output(self, event: RunOutputEvent) -> None:
        # Binary-mode bytes aren't stored in the snapshot tail — subscribers see them live.
        if not event.lines:
            return
        step = self._steps[event.step_index]
        joined = "\n".join(event.lines) + "\n"
        if event.fd == "stdout":
            step.stdout_tail = (step.stdout_tail + joined)[-OUTPUT_TAIL_CAP:]
        else:
            step.stderr_tail = (step.stderr_tail + joined)[-OUTPUT_TAIL_CAP:]
