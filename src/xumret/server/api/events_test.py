"""Tests for the /api/events SSE endpoint.

We can't drive SSE through `httpx.ASGITransport` (it buffers the entire
response) or `TestClient` (cross-thread `asyncio.Queue` is racy). Instead we
invoke `event_stream` directly with a minimal `Request` shim and iterate the
returned `StreamingResponse.body_iterator` in the same event loop where we
push events.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, cast

import pytest

from xumret.executor.dummy_executor import DummyExecutor
from xumret.executor.models import CommandStep, PhoneCommand, RunOption
from xumret.server.api import events as events_module
from xumret.single import SingleMain
from xumret.state.models import RunOutputEvent, RunStateCompleted
from xumret.state.phone import PhoneState


def _body_iter(response: Any) -> AsyncIterator[Any]:
    """The StreamingResponse body_iterator is an async generator; mypy
    can't see __anext__ through the abstract AsyncIterable annotation."""
    return cast(AsyncIterator[Any], response.body_iterator)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeRequest:
    """Minimal stand-in for `starlette.requests.Request` — `event_stream`
    only calls `request.is_disconnected()`.
    """

    def __init__(self) -> None:
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


def _make_service() -> tuple[SingleMain, PhoneState]:
    state = PhoneState()
    service = SingleMain(executor=DummyExecutor(), state=state)
    return service, state


@pytest.mark.anyio
async def test_sse_yields_run_state_frame() -> None:
    service, state = _make_service()
    req = _FakeRequest()
    response = await events_module.event_stream(cast(Any, req), svc=service)
    body_iter = _body_iter(response)

    state.submit(PhoneCommand(
        name="t",
        steps=[CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(slug="X"),
    ))
    # First frame: the `created` transition from submit.
    chunk = await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)
    text = chunk if isinstance(chunk, str) else chunk.decode()
    assert text.startswith("event: run_state\ndata: ")
    assert '"type": "created"' in text or '"type":"created"' in text

    # Push a completion event and read the next frame.
    run = state.get("X")
    assert run is not None
    run.emit(RunStateCompleted(slug="X", at=time.time()))
    chunk = await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)
    text = chunk if isinstance(chunk, str) else chunk.decode()
    assert "completed" in text

    # Disconnect: next iteration should end the generator.
    req.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)


@pytest.mark.anyio
async def test_sse_yields_run_output_frame() -> None:
    service, state = _make_service()
    req = _FakeRequest()
    response = await events_module.event_stream(cast(Any, req), svc=service)
    body_iter = _body_iter(response)

    state.submit(PhoneCommand(
        name="t",
        steps=[CommandStep(argv=["echo", "hi"])],
        run_option=RunOption(slug="X"),
    ))
    # Consume the 'created' frame.
    await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)

    run = state.get("X")
    assert run is not None
    run.emit(RunOutputEvent(
        slug="X", at=time.time(), step_index=0, fd="stdout", lines=["hi"],
    ))
    chunk = await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)
    text = chunk if isinstance(chunk, str) else chunk.decode()
    assert text.startswith("event: run_output\n")

    req.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)


@pytest.mark.anyio
async def test_sse_keepalive_when_idle(monkeypatch) -> None:
    """When `queue.get()` times out, the generator yields a keepalive comment."""
    real_wait_for = asyncio.wait_for

    async def fast_wait_for(awaitable, timeout):
        # The generator passes 30.0; shrink only that to keep the test snappy.
        if timeout == 30.0:
            timeout = 0.05
        return await real_wait_for(awaitable, timeout)

    monkeypatch.setattr(events_module.asyncio, "wait_for", fast_wait_for)

    service, _ = _make_service()
    req = _FakeRequest()
    response = await events_module.event_stream(cast(Any, req), svc=service)
    body_iter = _body_iter(response)

    chunk = await real_wait_for(body_iter.__anext__(), timeout=1.0)
    text = chunk if isinstance(chunk, str) else chunk.decode()
    assert text == ": keepalive\n\n"

    req.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await real_wait_for(body_iter.__anext__(), timeout=1.0)


@pytest.mark.anyio
async def test_sse_unsubscribes_on_exit() -> None:
    service, state = _make_service()
    before = len(state._subscribers)
    req = _FakeRequest()
    response = await events_module.event_stream(cast(Any, req), svc=service)
    body_iter = _body_iter(response)
    assert len(state._subscribers) == before + 1

    # End the generator cleanly: mark disconnected and pull until StopAsyncIteration.
    req.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(body_iter.__anext__(), timeout=1.0)

    assert len(state._subscribers) == before
