# server_bridge

The command protocol between state manager and executor. Shared by both sides in server-executor mode. Also used as plain in-process objects in single mode.

## models.py

`BridgeCommand` base class with discriminated subtypes:

**Server -> Executor:** `SubmitCommand`, `CancelCommand`, `QueryStatus`, `QueryDaemon`, `EndDaemon`

**Executor -> Server:** `SubmitOneshotResult`, `SubmitDaemonStarted`, `DaemonStatusReport`, `DaemonEnded`, `CommandError`

All reference types from `executor.models` (PhoneCommand, PhoneCommandResult, etc).

## ws.py

WS protocol, framing, reconnect logic. Serializes/deserializes BridgeCommand over WebSocket. Contains `RemoteExecutor` (implements `Executor` protocol by forwarding over WS). Not needed for single mode.
