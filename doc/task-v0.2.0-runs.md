# Task: v0.2.0 — Runs (subprocess management refresh)

Implementation checklist for the v0.2.0 subprocess-management work.
Design source of truth: [`design-process-management.md`](design-process-management.md).
Roadmap entry: [`roadmap.md`](roadmap.md).

## 0. Decisions (resolved — see [`design-process-management.md`](design-process-management.md))

- [x] **D1.** Submit endpoint = single `POST /api/runs`; slug in body.
- [x] **D2.** Output tail cap = **128 KiB per process** (per pipeline step),
  FIFO drop.
- [x] **D3.** Internal event delivery = per-subscriber `asyncio.Queue`.
- [x] **D4.** Late-subscriber semantics = client fetches `/state` then
  attaches to SSE for deltas. **No in-band snapshot event.** SSE has two
  event types: `run_state` (lifecycle transitions) and `run_output`
  (per-process incremental stdout/stderr).

## A. Run as live handle

Rebuild executor → state plumbing around per-run `Run` objects. Single mode
only at this stage; remote bridge stays out of scope.

### A.1 New / renamed types in `src/xumret/state/` and `src/xumret/executor/`

- [ ] Rename `CommandStatus → RunStatus` (`state/models.py`).
- [ ] Rename `CommandRecord → RunRecord` (`state/models.py`); replace
  `command_id` field with `slug`.
- [ ] Drop `CommandHandle` (subsumed by `Run`).
- [ ] Add `RunStateEvent` discriminated union: `created`, `step_started`
  (pid), `step_exited` (exit_code), `running`, `completed`, `failed`,
  `cancelled`, `daemon_started`, `daemon_status`, `daemon_ended`.
- [ ] Add `RunOutputEvent`: `{slug, step_index, fd: "stdout"|"stderr",
  lines?: list[str], bytes?: str (base64), dropped_lines?: int,
  dropped_bytes?: int}`. Drop counters are **deltas** since the previous
  event for that fd, not running totals.
- [ ] Add `StreamConfig(mode: "lines"|"binary"="lines",
  back_pressure: bool=False)` in `executor/models.py`.
- [ ] Extend `ProcessStep` with `stdout_stream: StreamConfig` and
  `stderr_stream: StreamConfig` (defaults to `StreamConfig()`).
- [ ] Add `Run` class (live handle): `slug`, `phone_command`, `created_at`,
  `status` property, `record` property, `emit(event)`, `subscribe()`.

### A.2 Executor refactor (`src/xumret/executor/local.py`)

- [ ] Replace `submit(SubmitCommand) -> Result` with `run(run: Run) -> None`.
  Executor calls `run.emit(...)` instead of returning values.
- [ ] Per-step lifecycle emission: `step_started` (pid), `step_exited`
  (exit_code), terminal `completed` / `failed` / `cancelled`.
- [ ] **Replace `proc.communicate()` with per-fd async reader tasks.** For
  each captured fd (every step's stderr; terminal-step stdout when not
  piped onward):
  - Spawn a reader task that reads chunks (binary) or lines
    (`asyncio.StreamReader.readline` with UTF-8 decode + `errors="replace"`)
    according to the step's `StreamConfig.mode`.
  - Append decoded data to a rolling 128 KiB tail buffer (per fd).
  - Emit `RunOutputEvent`s with `lines` or `bytes` populated according to
    the mode.
  - On `back_pressure=True`: pause reads when subscriber queues are full
    (let the OS pipe buffer fill, slowing the subprocess).
  - On `back_pressure=False`: always read; if a subscriber queue is full,
    drop the oldest output entry for that subscriber and accumulate
    `dropped_lines` / `dropped_bytes` to attach to the next event for that
    fd.
  - This unifies one-shot and daemon paths — both stream identically;
    daemons just stream longer.
- [ ] Daemon path emits `daemon_started` after spawn; `daemon_ended` on
  termination. `daemon_status` is only emitted on explicit query (no
  periodic polling).
- [ ] Cancel path: kill subprocesses, drain remaining output via the
  reader tasks, emit `cancelled`.

### A.3 PhoneState rewire (`src/xumret/state/phone.py`)

- [ ] Hold `slug → Run` map (live and unreaped-terminal both indexed here).
- [ ] Subscribe internally to each `Run`; mirror events into `RunRecord`
  for slim-record reads.
- [ ] Add a meta-channel: subscribers attaching to "all runs" get notified
  of new runs as they're created.
- [ ] Remove the old `command_id → CommandRecord` dict.

### A.4 SingleMain wiring (`src/xumret/single.py`)

- [ ] On `submit`, create a `Run`, hand it to `LocalExecutor.run(run)` as a
  background task, register it in `PhoneState`, return the `Run` (or its
  slim record).

### A.5 Tests

- [ ] `state/run_test.py`: `Run` emit/subscribe semantics, multi-subscriber.
- [ ] `state/phone_test.py`: slug index, mirror updates from emitted events.
- [ ] `executor/local_test.py`: per-step events emitted in order;
  cancellation path emits `cancelled` and kills processes.

## B. Slug + RunOption + reap

### B.1 Models

- [ ] Add `RunOption(slug: str | None = None, mutex_by_slug: bool = False)`
  in `executor/models.py`.
- [ ] Add `run_option: RunOption = RunOption()` field on `PhoneCommand`.
- [ ] (StreamConfig + per-step `stdout_stream`/`stderr_stream` already
  added in A.1.)

### B.2 Submit semantics (`PhoneState.submit`)

Implement the decision matrix from `design-process-management.md`:

- [ ] `slug=None` → auto-gen UUID4 slug; create fresh run.
- [ ] `slug=X, mutex_by_slug=False`, live `X` exists → return existing run.
- [ ] `slug=X, mutex_by_slug=False`, terminal-unreaped `X` exists → 409.
- [ ] `slug=X, mutex_by_slug=True`, live `X` exists → 409.
- [ ] `slug=X, mutex_by_slug=True`, terminal-unreaped `X` exists → 409.
- [ ] No collision → create fresh run, index by slug.

### B.3 Stop and reap

- [ ] `PhoneState.stop(slug)`: cancel live run; no-op on terminal; 404 on
  unknown slug.
- [ ] `PhoneState.reap(slug)`: remove terminal record, free slug; 404 on
  unknown or still-live slug (decide: 409 vs. 404 for live — lean 409 since
  the slug *is* live, just not terminal).

### B.4 Tests

- [ ] `state/phone_test.py`: every row of the decision matrix.
- [ ] Reap blocks when run is still live; succeeds when terminal.
- [ ] Stop on already-terminal is no-op success; stop on unknown is 404.

## C. HTTP API migration

Rename to `/api/runs/...` and add the new endpoints. Verbs limited to GET /
PUT / POST per `design-process-management.md`; remove DELETE.

### C.1 Routes (`src/xumret/server/api/routes.py`)

- [ ] `POST /api/runs` — submit; takes `PhoneCommand` body.
- [ ] `GET /api/runs` — list slim records.
- [ ] `GET /api/runs/{slug}` — slim record; 404 if unknown.
- [ ] `GET /api/runs/{slug}/state` — rich state: `RunRecord` + transition
  log + per-step output tails (128 KiB cap per process).
- [ ] `POST /api/runs/{slug}/stop` — cancel live run.
- [ ] `POST /api/runs/{slug}/reap` — reap terminal run.
- [ ] **Remove** `DELETE /api/commands/{id}`.
- [ ] `GET /api/events` (kept) — SSE emits two event categories:
  `run_state` (lifecycle deltas) and `run_output` (incremental
  stdout/stderr chunks). Rename internal payloads `command_*` → `run_*`.

### C.2 Service interface (`src/xumret/protocol/service.py`)

- [ ] Replace `submit / get / list / cancel / query_daemon / end_daemon`
  with `submit / get / list / get_state / stop / reap`. Daemon-specific
  methods collapse into the unified surface (daemon-ness is internal to
  the run, not a separate API concept).

### C.3 Bridge models (`src/xumret/server_bridge/models.py`)

Out of scope for this task — bridge work happens later. Leave models in
place but mark with a comment that they need a parallel rename when
bridge work begins.

### C.4 Tests

- [ ] `server/api/routes_test.py`: each endpoint, each happy + error path.
- [ ] Idempotency: repeated submit with same slug returns same handle;
  repeated stop is no-op; reap-then-reap is 404.

## D. WebUI adaptation (`webui-src/`)

### D.1 API client

- [ ] Update fetch paths from `/api/commands/...` to `/api/runs/...`.
- [ ] Add helpers for `/state`, `/stop`, `/reap`.
- [ ] SSE event-name mapping updated (`command_*` → `run_*`).

### D.2 UI flows

- [ ] Per-run detail view consumes `/state` for transitions + output
  buffers; renders per-step progress (step_started / step_exited).
- [ ] Submit form exposes `slug` and `mutex_by_slug` inputs (advanced
  section; default unchecked / blank for fire-and-forget).
- [ ] Action buttons: Stop (when live), Reap (when terminal).
- [ ] Conflict (409) on submit surfaces a user-readable message:
  "A run with this slug is already active; stop or reap it first."

### D.3 Smoke check

- [ ] `make webui-dev` against `xumret single` on the phone — submit a
  one-shot, watch step events stream over SSE, reap, re-submit.

## Acceptance

- All code paths covered by tests above pass `make test`.
- `make webui-dev` smoke flow works against a real phone (one-shot +
  daemon both observable end-to-end).
- `design-process-management.md` open decisions are pinned (no `Lean: ...` markers
  left).
- `journals/` entry written summarising what shipped and any deviations
  from the design.

## Out of scope for v0.2.0

- `RemoteExecutor` / `server_bridge/ws.py` (server-executor mode).
- Disconnect-recovery policy on reconnect.
- Auto-reap of fire-and-forget runs.
- TTL-based zombie GC.
- `design-command-compose.md` (separate roadmap item).
