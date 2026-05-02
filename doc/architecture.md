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
├── protocol/
│   ├── executor.py          # Executor protocol (speaks BridgeCommand types)
│   └── service.py           # XumretService protocol (async, what routes depend on)
│
├── executor/
│   ├── models.py            # PhoneCommand, ProcessStep, Connection types
│   ├── local.py             # LocalExecutor: runs processes via termux-api
│   └── agent.py             # Phone-side WS agent wrapping LocalExecutor
│
├── single.py                # SingleMain: single mode orchestrator
│
├── state/
│   ├── models.py            # CommandStatus, CommandRecord, CommandHandle, StateEvent
│   └── phone.py             # PhoneState: pure state container (sync, no executor)
│
├── server/
│   └── api/
│       ├── app.py           # FastAPI app factory (injects XumretService)
│       ├── routes.py        # REST endpoints (via Depends on XumretService)
│       └── events.py        # SSE for real-time updates to WebUI
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
                 ┌──────────────────────────────────────────────────────────┐
                 │  single process (phone)                                  │
                 │                                                          │
WebUI ──HTTP──>  │  api ──Depends──> SingleMain ──> LocalExecutor ──> subprocess
                 │   │                  │                            (termux-api)
                 │   │                  └── PhoneState                       │
                 │   └── static assets (webui-assets/)                      │
                 └──────────────────────────────────────────────────────────┘
```

- `api/` routes depend on `XumretService` protocol via FastAPI DI
- `SingleMain` implements `XumretService`, owns `Executor` + `PhoneState`
- `PhoneState` is a pure state container — no executor reference
- `server_bridge.models` types are used as plain in-process objects — no serialization

### Server-executor

```
 Server process (PC):
 ┌──────────────────────────────────────────────────────────┐
 │                                                          │
 │  api ──Depends──> ServerMain ──> RemoteExecutor ──WS──┐  │
 │   │                  │          (server_bridge)       │  │
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

- `api/` routes depend on `XumretService` protocol — same as single mode
- `ServerMain` implements `XumretService`, manages multiple `PhoneState`s + `RemoteExecutor`s
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

Source in `webui-src/`, built output in `webui-assets/`. React + TypeScript + PrimeReact. Talks to the API over HTTP + SSE. Same frontend regardless of mode.

### Mechanism vs policy

The Python backend (executor, state, API) provides **mechanism**: start processes, collect output, track lifecycle. It has no knowledge of termux-api semantics.

The WebUI provides **policy**: it knows which termux-api commands to compose for a use case (e.g. "show SMS inbox" = submit `termux-sms-list`, render results as a message table). Domain-specific workflows live entirely in the frontend.
