# state

Run lifecycle types and per-phone Run registry. No executor references.

## models.py

- `RunStatus` enum: pending, running, completed, failed, cancelled, timed_out
- `RunStateEvent` discriminated union: created, step_started (pid),
  step_exited (exit_code), running, completed, failed (error), cancelled,
  timed_out
- `RunOutputEvent`: per-step incremental stdout/stderr
  (`lines?` / `bytes?` (base64))
- `RunRecord`: materialized snapshot — slug, phone_command, status, steps[],
  transitions[], timestamps. Also serves as the API response shape.
- `StepState`: per-step pid, exit_code, stdout/stderr tails (128 KiB cap)

`TERMINAL_STATUSES`: completed / failed / cancelled / timed_out.

## run.py

`Run` — live, subscribable handle for one execution.

- `slug`, `phone_command`, `created_at`
- `status`, `is_live`, `is_terminal`
- `record` — current materialized `RunRecord`
- Construction takes an optional `on_event: Callable[[RunEvent], None]`
  invoked synchronously during `emit()`. `PhoneState` uses it to fan events
  out to phone-wide subscribers.
- `emit(event)` — apply to internal state, call `on_event` (sync), broadcast
  to subscriber queues
- `subscribe()` / `unsubscribe(q)` — async queue per consumer

## phone.py

`PhoneState` — slug-keyed registry of Runs for one phone.

**Queries:** `get(slug)`, `list()`

**Mutations:**
- `submit(phone_command)` — applies the slug decision matrix
  (`doc/design-process-management.md`); returns existing live run on
  idempotent join, raises `SubmitConflict` on terminal-unreaped or live-mutex
  collision, otherwise creates a fresh `Run` with `on_event` bound to the
  phone-wide broadcaster.
- `reap(slug)` — removes a terminal run; raises `StillLive` for live runs,
  `UnknownSlug` if missing.

**Phone-wide SSE:** `subscribe()` / `unsubscribe(q)`. Fan-out is sync (each
Run has `on_event=self._broadcast`), so emit doesn't require a running event
loop.
