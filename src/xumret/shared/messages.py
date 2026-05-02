"""Message types for xumret protocol."""

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


def make_ts() -> int:
    """Current timestamp in seconds."""
    return int(time.time())


def make_id() -> str:
    """Generate unique command ID."""
    return str(uuid.uuid4())


class Message(BaseModel):
    """Base message envelope."""

    type: str
    seq: int = 0
    ts: int = Field(default_factory=make_ts)
    payload: dict[str, Any] = Field(default_factory=dict)


# Client -> Server messages


class Hello(Message):
    """Client identification on connect."""

    type: Literal["HELLO"] = "HELLO"
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(cls, client_id: str, client_name: str) -> "Hello":
        return cls(payload={"client_id": client_id, "client_name": client_name})


class Pong(Message):
    """Keepalive response."""

    type: Literal["PONG"] = "PONG"


class CmdResult(Message):
    """Command execution result."""

    type: Literal["CMD_RESULT"] = "CMD_RESULT"

    @classmethod
    def create(cls, cmd_id: str, status: str, data: Any, seq: int = 0) -> "CmdResult":
        return cls(seq=seq, payload={"id": cmd_id, "status": status, "data": data})


class CmdError(Message):
    """Command execution error."""

    type: Literal["CMD_ERROR"] = "CMD_ERROR"

    @classmethod
    def create(cls, cmd_id: str, error: str, seq: int = 0) -> "CmdError":
        return cls(seq=seq, payload={"id": cmd_id, "error": error})


class Event(Message):
    """Async event from device."""

    type: Literal["EVENT"] = "EVENT"

    @classmethod
    def create(cls, event: str, data: Any, seq: int = 0) -> "Event":
        return cls(seq=seq, payload={"event": event, "data": data})


# Server -> Client messages


class Ping(Message):
    """Keepalive request."""

    type: Literal["PING"] = "PING"


class Cmd(Message):
    """Command to execute."""

    type: Literal["CMD"] = "CMD"

    @classmethod
    def create(
        cls, cmd: str, args: dict[str, Any] | None = None, seq: int = 0
    ) -> "Cmd":
        cmd_id = make_id()
        return cls(seq=seq, payload={"id": cmd_id, "cmd": cmd, "args": args or {}})


# Message parsing

MESSAGE_TYPES: dict[str, type[Message]] = {
    "HELLO": Hello,
    "PONG": Pong,
    "CMD_RESULT": CmdResult,
    "CMD_ERROR": CmdError,
    "EVENT": Event,
    "PING": Ping,
    "CMD": Cmd,
}


def parse_message(data: str) -> Message:
    """Parse JSON string into appropriate Message type."""
    import json

    obj = json.loads(data)
    msg_type = obj.get("type")
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"Unknown message type: {msg_type}")
    return MESSAGE_TYPES[msg_type].model_validate(obj)


def serialize_message(msg: Message) -> str:
    """Serialize message to JSON string."""
    return msg.model_dump_json()
