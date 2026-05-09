from __future__ import annotations

import asyncio
import time

import pytest

from xumret.executor.models import PhoneCommand, ProcessStep, RunOption
from xumret.state.models import (
    RunStateCancelled,
    RunStateCompleted,
    RunStateRunning,
)
from xumret.state.phone import (
    PhoneState,
    StillLive,
    SubmitConflict,
    UnknownSlug,
)


def _pc(*, slug: str | None = None, mutex: bool = False) -> PhoneCommand:
    return PhoneCommand(
        name="t",
        steps=[ProcessStep(argv=["echo", "hi"])],
        connections=[],
        run_option=RunOption(slug=slug, mutex_by_slug=mutex),
    )


def _force_terminal(state: PhoneState, slug: str) -> None:
    run = state.get(slug)
    assert run is not None
    run.emit(RunStateCompleted(slug=slug, at=time.time()))


# --- submit decision matrix ---


def test_submit_auto_generates_slug_when_none():
    state = PhoneState()
    run = state.submit(_pc())
    assert run.slug
    assert state.get(run.slug) is run


def test_submit_with_caller_slug_uses_it():
    state = PhoneState()
    run = state.submit(_pc(slug="my-slug"))
    assert run.slug == "my-slug"


def test_submit_join_when_live_same_slug_no_mutex():
    state = PhoneState()
    first = state.submit(_pc(slug="X"))
    second = state.submit(_pc(slug="X"))
    assert first is second  # idempotent join


def test_submit_409_when_terminal_unreaped_no_mutex():
    state = PhoneState()
    state.submit(_pc(slug="X"))
    _force_terminal(state, "X")
    with pytest.raises(SubmitConflict) as ei:
        state.submit(_pc(slug="X"))
    assert ei.value.reason == "terminal-unreaped"


def test_submit_409_when_live_with_mutex():
    state = PhoneState()
    state.submit(_pc(slug="X"))
    with pytest.raises(SubmitConflict) as ei:
        state.submit(_pc(slug="X", mutex=True))
    assert ei.value.reason == "live-mutex"


def test_submit_409_when_terminal_unreaped_with_mutex():
    state = PhoneState()
    state.submit(_pc(slug="X"))
    _force_terminal(state, "X")
    with pytest.raises(SubmitConflict) as ei:
        state.submit(_pc(slug="X", mutex=True))
    assert ei.value.reason == "terminal-unreaped"


def test_submit_fresh_after_reap():
    state = PhoneState()
    state.submit(_pc(slug="X"))
    _force_terminal(state, "X")
    state.reap("X")
    run = state.submit(_pc(slug="X"))
    assert run.slug == "X"


# --- get / list ---


def test_get_existing_returns_run():
    state = PhoneState()
    run = state.submit(_pc(slug="X"))
    assert state.get("X") is run


def test_get_missing_returns_none():
    state = PhoneState()
    assert state.get("nope") is None


def test_list_returns_all():
    state = PhoneState()
    state.submit(_pc(slug="a"))
    state.submit(_pc(slug="b"))
    slugs = {r.slug for r in state.list()}
    assert slugs == {"a", "b"}


# --- reap ---


def test_reap_terminal_succeeds():
    state = PhoneState()
    state.submit(_pc(slug="X"))
    _force_terminal(state, "X")
    state.reap("X")
    assert state.get("X") is None


def test_reap_live_raises_still_live():
    state = PhoneState()
    state.submit(_pc(slug="X"))
    with pytest.raises(StillLive):
        state.reap("X")


def test_reap_unknown_raises():
    state = PhoneState()
    with pytest.raises(UnknownSlug):
        state.reap("nope")


# --- subscriptions ---


def test_phone_subscriber_sees_created_on_submit():
    state = PhoneState()
    q = state.subscribe()
    state.submit(_pc(slug="X"))
    assert not q.empty()
    ev = q.get_nowait()
    assert ev.type == "created"
    assert ev.slug == "X"


def test_phone_subscriber_sees_events_from_multiple_runs():
    state = PhoneState()
    q = state.subscribe()
    state.submit(_pc(slug="a"))
    state.submit(_pc(slug="b"))
    seen: list[str] = []
    while not q.empty():
        seen.append(q.get_nowait().slug)
    assert "a" in seen and "b" in seen


def test_phone_subscriber_sees_run_transitions():
    state = PhoneState()
    q = state.subscribe()
    state.submit(_pc(slug="X"))
    run = state.get("X")
    run.emit(RunStateRunning(slug="X", at=time.time()))
    types: list[str] = []
    while not q.empty():
        types.append(q.get_nowait().type)
    assert types == ["created", "running"]


def test_unsubscribe_stops_delivery():
    state = PhoneState()
    q = state.subscribe()
    state.unsubscribe(q)
    state.submit(_pc(slug="X"))
    assert q.empty()


def test_unsubscribe_unknown_queue_is_noop():
    state = PhoneState()
    state.unsubscribe(asyncio.Queue())  # should not raise


def test_reap_stops_forwarding_for_that_run():
    state = PhoneState()
    q = state.subscribe()
    state.submit(_pc(slug="X"))
    _force_terminal(state, "X")
    # Drain
    while not q.empty():
        q.get_nowait()
    run_X = state.get("X")
    state.reap("X")
    # Emitting on the (now-detached) Run should not feed phone subscribers.
    run_X.emit(RunStateCancelled(slug="X", at=time.time()))
    assert q.empty()
