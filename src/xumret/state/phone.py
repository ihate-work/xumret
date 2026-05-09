"""PhoneState — slug-keyed registry of Runs for one phone.

Holds `slug → Run`. Implements the submit decision matrix
(see `doc/design-process-management.md`):

| slug   | mutex_by_slug | live? | terminal-unreaped? | result        |
|--------|---------------|-------|--------------------|---------------|
| None   | n/a           | n/a   | n/a                | new run       |
| "X"    | False         | yes   | -                  | join existing |
| "X"    | False         | no    | yes                | 409           |
| "X"    | False         | no    | no                 | new run       |
| "X"    | True          | yes   | -                  | 409           |
| "X"    | True          | no    | yes                | 409           |
| "X"    | True          | no    | no                 | new run       |

Phone-wide subscribers see every event from every run via a sync listener
hook on each Run, so the broadcast path needs no running event loop.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import ihate_work.o11y as o11y

from xumret.executor.models import PhoneCommand
from xumret.state.models import RunEvent, RunStateCreated
from xumret.state.run import Run

logger, *_ = o11y.get_o11y(__name__)


class SubmitConflict(Exception):
    """Slug already in use; client must reap or pick a different slug."""

    def __init__(self, slug: str, *, reason: str) -> None:
        super().__init__(f"slug {slug!r} conflict: {reason}")
        self.slug = slug
        self.reason = reason


class UnknownSlug(Exception):
    def __init__(self, slug: str) -> None:
        super().__init__(f"unknown slug: {slug!r}")
        self.slug = slug


class StillLive(Exception):
    """Reap attempted on a still-live run."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"slug {slug!r} is still live; stop it first")
        self.slug = slug


class PhoneState:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._subscribers: list[asyncio.Queue[RunEvent]] = []

    # --- queries ---

    def get(self, slug: str) -> Run | None:
        return self._runs.get(slug)

    def list(self) -> list[Run]:
        return list(self._runs.values())

    # --- mutations ---

    def submit(self, phone_command: PhoneCommand) -> Run:
        opt = phone_command.run_option
        if opt.slug is not None:
            existing = self._runs.get(opt.slug)
            if existing is not None:
                if existing.is_terminal:
                    raise SubmitConflict(opt.slug, reason="terminal-unreaped")
                # live
                if opt.mutex_by_slug:
                    raise SubmitConflict(opt.slug, reason="live-mutex")
                return existing  # idempotent join
            slug = opt.slug
        else:
            slug = uuid.uuid4().hex

        run = Run(slug=slug, phone_command=phone_command)
        run.add_listener(self._broadcast)
        self._runs[slug] = run
        run.emit(RunStateCreated(slug=slug, at=time.time()))
        return run

    def reap(self, slug: str) -> None:
        run = self._runs.get(slug)
        if run is None:
            raise UnknownSlug(slug)
        if run.is_live:
            raise StillLive(slug)
        run.remove_listener(self._broadcast)
        del self._runs[slug]

    # --- subscriptions (phone-wide fan-out) ---

    def subscribe(self) -> asyncio.Queue[RunEvent]:
        q: asyncio.Queue[RunEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[RunEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    # --- internal ---

    def _broadcast(self, event: RunEvent) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass
