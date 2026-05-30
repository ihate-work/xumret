# server_bridge

Server↔executor wire protocol.

OUT OF SCOPE for v0.2.0. The previous content was tied to the pre-Run
`command_id` protocol and has been removed. Bridge work resumes in a later
milestone, at which point this package will:

- forward submit / stop / reap / query_daemon_status as messages
- forward `RunStateEvent` and `RunOutputEvent` back to the controller
- use `slug` as the unified identifier

See `doc/design-process-management.md`.
