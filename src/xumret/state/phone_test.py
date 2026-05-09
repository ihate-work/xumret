from __future__ import annotations

import asyncio

from xumret.executor.models import (
    PhoneCommand,
    PhoneCommandDaemonHandle,
    PhoneCommandResult,
    ProcessResult,
    ProcessStep,
)
from xumret.state.models import CommandStatus
from xumret.state.phone import PhoneState


def _make_pc(name: str = "test") -> PhoneCommand:
    return PhoneCommand(
        name=name,
        steps=[ProcessStep(argv=["echo", "hi"])],
        connections=[],
    )


# --- create / get / list ---


def test_create_returns_pending_record():
    state = PhoneState()
    record = state.create(command_id="cmd-1", phone_command=_make_pc())
    assert record.command_id == "cmd-1"
    assert record.status == CommandStatus.pending
    assert record.phone_command.name == "test"
    assert record.created_at > 0
    assert record.updated_at == record.created_at


def test_get_existing():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    assert state.get("cmd-1") is not None
    assert state.get("cmd-1").command_id == "cmd-1"


def test_get_missing():
    state = PhoneState()
    assert state.get("nope") is None


def test_list_empty():
    state = PhoneState()
    assert state.list() == []


def test_list_multiple():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    state.create(command_id="cmd-2", phone_command=_make_pc())
    ids = {r.command_id for r in state.list()}
    assert ids == {"cmd-1", "cmd-2"}


# --- state transitions ---


def test_set_running():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    state.set_running("cmd-1")
    record = state.get("cmd-1")
    assert record.status == CommandStatus.running
    assert record.updated_at >= record.created_at


def test_set_completed():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    state.set_running("cmd-1")
    result = PhoneCommandResult(
        command_id="cmd-1",
        steps=[ProcessResult(exit_code=0, stdout="ok", stderr="")],
    )
    state.set_completed("cmd-1", result=result)
    record = state.get("cmd-1")
    assert record.status == CommandStatus.completed
    assert record.result == result


def test_set_failed():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    state.set_running("cmd-1")
    state.set_failed("cmd-1", error="boom")
    record = state.get("cmd-1")
    assert record.status == CommandStatus.failed
    assert record.error == "boom"


def test_set_cancelled():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    state.set_running("cmd-1")
    state.set_cancelled("cmd-1")
    assert state.get("cmd-1").status == CommandStatus.cancelled


def test_set_daemon_started():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    handle = PhoneCommandDaemonHandle(command_id="cmd-1", handle_id="h-1")
    state.set_daemon_started("cmd-1", handle=handle)
    record = state.get("cmd-1")
    assert record.daemon_handle == handle


def test_set_daemon_ended():
    state = PhoneState()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    handle = PhoneCommandDaemonHandle(command_id="cmd-1", handle_id="h-1")
    state.set_daemon_started("cmd-1", handle=handle)
    state.set_daemon_ended("h-1")
    assert state.get("cmd-1").status == CommandStatus.completed


def test_set_daemon_ended_unknown_handle():
    state = PhoneState()
    state.set_daemon_ended("ghost")  # should not raise


# --- subscriptions ---


def test_subscribe_receives_events():
    state = PhoneState()
    queue = state.subscribe()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    assert not queue.empty()
    event = queue.get_nowait()
    assert event.type == "command_submitted"
    assert event.command_id == "cmd-1"


def test_multiple_transitions_emit_events():
    state = PhoneState()
    queue = state.subscribe()
    state.create(command_id="cmd-1", phone_command=_make_pc())
    state.set_running("cmd-1")
    state.set_failed("cmd-1", error="oops")
    types = []
    while not queue.empty():
        types.append(queue.get_nowait().type)
    assert types == ["command_submitted", "command_running", "command_failed"]


def test_unsubscribe_stops_events():
    state = PhoneState()
    queue = state.subscribe()
    state.unsubscribe(queue)
    state.create(command_id="cmd-1", phone_command=_make_pc())
    assert queue.empty()


def test_unsubscribe_unknown_queue():
    state = PhoneState()
    state.unsubscribe(asyncio.Queue())  # should not raise
