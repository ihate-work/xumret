from __future__ import annotations

import asyncio
import json

from xumret.executor.dummy_executor import DummyExecutor
from xumret.executor.models import PhoneCommand, ProcessStep
from xumret.server_bridge.models import (
    CancelCommand,
    EndDaemon,
    QueryDaemon,
    QueryStatus,
    SubmitCommand,
    SubmitDaemonStarted,
    SubmitOneshotResult,
)


def _make_submit(
    command_id: str = "cmd-1",
    daemon: bool = False,
    argv: list[str] | None = None,
    steps: int = 1,
) -> SubmitCommand:
    if argv is not None:
        step_list = [ProcessStep(argv=argv)]
    else:
        step_list = [ProcessStep(argv=["echo", "hi"]) for _ in range(steps)]
    return SubmitCommand(
        command_id=command_id,
        phone_command=PhoneCommand(
            name="test",
            steps=step_list,
            connections=[],
            daemon=daemon,
        ),
    )


def test_oneshot_returns_result() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(steps=2))
        assert isinstance(resp, SubmitOneshotResult)
        assert resp.result.command_id == "cmd-1"
        assert len(resp.result.steps) == 2
        for step in resp.result.steps:
            assert step.exit_code == 0

    asyncio.run(run())


def test_canned_battery_status() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(argv=["termux-battery-status"]))
        assert isinstance(resp, SubmitOneshotResult)
        data = json.loads(resp.result.steps[0].stdout)
        assert data["percentage"] == 72
        assert data["plugged"] == "UNPLUGGED"

    asyncio.run(run())


def test_canned_sms_list() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(argv=["termux-sms-list"]))
        assert isinstance(resp, SubmitOneshotResult)
        data = json.loads(resp.result.steps[0].stdout)
        assert len(data) == 2
        assert data[0]["type"] == "inbox"

    asyncio.run(run())


def test_silent_command_returns_empty() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(argv=["termux-toast", "hello"]))
        assert isinstance(resp, SubmitOneshotResult)
        assert resp.result.steps[0].stdout == ""

    asyncio.run(run())


def test_unknown_binary_returns_stub() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(argv=["my-script", "--flag"]))
        assert isinstance(resp, SubmitOneshotResult)
        data = json.loads(resp.result.steps[0].stdout)
        assert data["dummy"] is True
        assert data["argv"] == ["my-script", "--flag"]

    asyncio.run(run())


def test_daemon_returns_handle() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(daemon=True))
        assert isinstance(resp, SubmitDaemonStarted)
        assert resp.handle.command_id == "cmd-1"
        assert resp.handle.handle_id

    asyncio.run(run())


def test_cancel_records_command() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        await executor.cancel(CancelCommand(command_id="cmd-1"))
        assert "cmd-1" in executor._cancelled

    asyncio.run(run())


def test_query_status_found() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(daemon=True))
        assert isinstance(resp, SubmitDaemonStarted)
        status = await executor.query_status(QueryStatus(command_id="cmd-1"))
        assert status.status.all_running is True

    asyncio.run(run())


def test_query_status_not_found() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.query_status(QueryStatus(command_id="no-such"))
        assert resp.error == "not_found"

    asyncio.run(run())


def test_query_daemon_found() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(daemon=True))
        assert isinstance(resp, SubmitDaemonStarted)
        status = await executor.query_daemon(QueryDaemon(handle_id=resp.handle.handle_id))
        assert status.status.all_running is True

    asyncio.run(run())


def test_query_daemon_not_found() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        status = await executor.query_daemon(QueryDaemon(handle_id="ghost"))
        assert status.status.all_running is False
        assert status.status.steps == []

    asyncio.run(run())


def test_end_daemon() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        resp = await executor.submit(_make_submit(daemon=True))
        assert isinstance(resp, SubmitDaemonStarted)
        handle_id = resp.handle.handle_id

        ended = await executor.end_daemon(EndDaemon(handle_id=handle_id))
        assert ended.handle_id == handle_id

        status = await executor.query_daemon(QueryDaemon(handle_id=handle_id))
        assert status.status.all_running is False

    asyncio.run(run())


def test_end_daemon_unknown() -> None:
    executor = DummyExecutor()

    async def run() -> None:
        ended = await executor.end_daemon(EndDaemon(handle_id="nope"))
        assert ended.handle_id == "nope"
        assert ended.final_steps == []

    asyncio.run(run())
