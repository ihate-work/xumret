# state

Pure state container for command lifecycle tracking. No executor references, no orchestration.

## models.py

Data types shared by state and service layers:

- `CommandStatus` enum: pending, running, completed, failed, cancelled
- `CommandRecord`: full command state (id, phone_command, status, result, daemon_handle, error, timestamps)
- `CommandHandle`: lightweight receipt returned from submit (id, status, created_at)
- `StateEvent`: pushed to SSE subscribers on every transition (type, command_id, data)

## phone.py

`PhoneState` — pure sync state container for one phone's commands.

**Queries:** `get(command_id)`, `list()`

**Mutations:** `create(...)`, `set_running(...)`, `set_completed(...)`, `set_failed(...)`, `set_cancelled(...)`, `set_daemon_started(...)`, `set_daemon_ended(...)`

Each mutation updates timestamps and emits a `StateEvent` to subscribers.

**SSE:** `subscribe()` returns an `asyncio.Queue[StateEvent]`, `unsubscribe()` removes it.
