# executor

Runs commands on the phone via termux-api.

## models.py

`PhoneCommand` defines a pipeline of processes (`ProcessStep`, each an `argv: list[str]`) connected by typed `Connection`s (`Pipe` for stdout->stdin, `TempFile` for file-based handoff). Extensible to NamedPipe, Socket, etc.

Two variants via `daemon` flag:
- **One-shot** (`daemon=False`): blocks until exit, returns `PhoneCommandResult` (per-step exit code + stdout/stderr).
- **Daemon** (`daemon=True`): returns `PhoneCommandDaemonHandle` immediately. Query with `query_daemon`, stop with `end_daemon`.

## protocol.py

`Executor` Protocol — the abstraction boundary. `StateManager` talks to this, never to a concrete implementation.

Methods: `submit`, `cancel`, `query_status`, `query_daemon`, `end_daemon`. All speak `server_bridge.models` types.

## local.py

`LocalExecutor` — implements `Executor` by running subprocesses directly. Used in single mode.

## agent.py

`ExecutorAgent` — phone-side WS agent. Wraps a `LocalExecutor` behind the `server_bridge` WS protocol. Used in server-executor mode.
