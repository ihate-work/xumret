"""Wire-protocol models for the server↔executor bridge.

OUT OF SCOPE for v0.2.0. The previous content (CommandStatus, SubmitCommand,
CancelCommand, daemon report types, etc.) was tied to the pre-Run command-id
protocol and has been removed alongside the executor-protocol rewrite.

When bridge work resumes (`server_bridge/ws.py`, `RemoteExecutor`), this file
needs a fresh design around the new `Run` lifecycle:

- forward submit / stop / reap / query_daemon_status as messages
- forward `RunStateEvent` and `RunOutputEvent` back to the controller
- use `slug` as the unified identifier

See `doc/design-process-management.md`.
"""
