# Architecture

`xumret` is a remote control for termux and termux-api. It can work in 2 modes:

- **single** mode: one Python process on the phone. Hosts the controller WebUI (static assets), executes commands via termux-api, tracks their state, and exposes the controller HTTP API (including SSE).

- **server-executor** mode: two processes on two hosts. The phone runs an *executor* that runs commands. A *server* on another machine (PC, cloud) keeps state and serves the WebUI. Executor and server communicate over WebSocket.

## Use cases

```sh
# single: everything on phone
phone $ xumret single

# server-executor: split across hosts
phone $ xumret executor --server-addr=SERVER_ADDR --server-secret=SECRET
pc    $ xumret server --secret=SECRET
```

## Package layout

```
src/xumret/
├── __init__.py
├── __main__.py              # CLI (click): wires mode-specific pieces
│
├── executor/
│   ├── models.py            # PhoneCommand, ProcessStep, Connection types
│   ├── protocol.py          # Executor protocol (speaks BridgeCommand types)
│   ├── local.py             # LocalExecutor: runs processes via termux-api
│   └── agent.py             # Phone-side WS agent wrapping LocalExecutor
│
├── state/
│   └── manager.py           # StateManager: command lifecycle, result collection
│
├── api/
│   ├── app.py               # FastAPI app factory
│   ├── routes.py            # REST endpoints (submit command, query status, ...)
│   └── events.py            # SSE for real-time updates to WebUI
│
├── server_bridge/
│   ├── models.py            # BridgeCommand, SubmitCommand, StatusReport, ...
│   └── ws.py                # WS protocol, framing, reconnect logic
│
└── models/                  # (reserved) shared types if needed beyond the above
```

## Composition per mode

### Single

```
                 ┌─────────────────────────────────────────────────┐
                 │  single process (phone)                         │
                 │                                                 │
WebUI ──HTTP──>  │  api ──> StateManager ──> LocalExecutor ──> subprocess
                 │   │                                        (termux-api)
                 │   └── static assets (webui-assets/)             │
                 └─────────────────────────────────────────────────┘
```

- `api/` serves HTTP + SSE + static files
- `StateManager` holds a `LocalExecutor` directly (in-process)
- `server_bridge.models` types are used as plain in-process objects — no serialization

### Server-executor

```
 Server process (PC):
 ┌──────────────────────────────────────────────────────────┐
 │                                                          │
 │  api ──> StateManager ──> RemoteExecutor ──WS──┐        │
 │   │                       (server_bridge)       │        │
 │   └── static assets                             │        │
 └─────────────────────────────────────────────────│────────┘
                                                   │
 Phone process:                                    │
 ┌─────────────────────────────────────────────────│────────┐
 │                                                 │        │
 │  ExecutorAgent ◀────────────────────────────────┘        │
 │      │          (server_bridge)                          │
 │      └──> LocalExecutor ──> subprocess (termux-api)      │
 │                                                          │
 └──────────────────────────────────────────────────────────┘
```

- `StateManager` talks to `RemoteExecutor` which implements the `Executor` protocol over WS
- Phone-side `ExecutorAgent` wraps `LocalExecutor` behind the same WS protocol
- Both sides import `server_bridge` for shared WS protocol + message types

## API for WebUI

The HTTP API served by `api/` is the same in both modes. The WebUI does not know which mode is running.

```
POST   /api/commands          submit a command
GET    /api/commands           list commands + status
GET    /api/commands/{id}      get single command status
DELETE /api/commands/{id}      cancel a command
GET    /api/events             SSE stream of real-time updates
```

## Implementation order

1. **Single mode first**: `api/`, `state/`, `executor/local.py`, `executor/models.py`, `server_bridge/models.py`, `executor/protocol.py`
2. **Server-executor mode**: `server_bridge/ws.py`, `executor/agent.py`, `RemoteExecutor`
3. **WebUI**: build out `xumret-controller` against the HTTP API

## WebUI

See `xumret-controller/` (React + TypeScript + Tailwind). Talks to the API over HTTP + SSE. Same frontend regardless of mode.
