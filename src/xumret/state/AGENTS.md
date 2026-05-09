# state

Run lifecycle types and per-phone Run registry. No executor references.

## models.py

Data types shared by state and service layers:

- `RunStatus` enum: pending, running, completed, failed, cancelled
- `RunStateEvent` discriminated union: created, step_started (pid),
  step_exited (exit_code), running, completed, failed (error), cancelled,
  daemon_started, daemon_status, daemon_ended
- `RunOutputEvent`: per-step incremental stdout/stderr
  (`lines?` / `bytes?` (base64) / `dropped_lines?` / `dropped_bytes?`)
- `RunRecord`: materialized snapshot — slug, phone_command, status, steps[],
  transitions[], timestamps. Also serves as the API response shape.
- `StepState`: per-step pid, exit_code, stdout/stderr tails (128 KiB cap),
  drop counters

`TERMINAL_STATUSES`: completed / failed / cancelled.

## run.py

`Run` — live, subscribable handle for one execution.

- `slug`, `phone_command`, `created_at`
- `status`, `is_live`, `is_terminal`
- `record` — current materialized `RunRecord`
- `emit(event)` — apply to internal state, fire listeners (sync), broadcast
  to subscriber queues
- `subscribe()` / `unsubscribe(q)` — async queue per consumer
- `add_listener(fn)` / `remove_listener(fn)` — sync callback during emit

## phone.py

`PhoneState` — slug-keyed registry of Runs for one phone.

**Queries:** `get(slug)`, `list()`

**Mutations:**
- `submit(phone_command)` — applies the slug decision matrix (see
  `doc/design-process-management.md`); returns existing live run on
  idempotent join, raises `SubmitConflict` on terminal-unreaped or
  live-mutex collision, otherwise creates a fresh `Run`.
- `reap(slug)` — removes a terminal run; raises `StillLive` for live runs,
  `UnknownSlug` if missing.

**Phone-wide SSE:** `subscribe()` / `unsubscribe(q)`. Fan-out is sync (a
listener on each Run), so no event loop is required to emit.
