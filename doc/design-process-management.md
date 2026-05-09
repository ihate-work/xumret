# Plan: Runs as live, subscribable handles

Motivated by reading the `xumret-alt` prototype
(`/Users/mono/vibra/xumret-alt/xumret/`) and noticing that its `StateEmitter`
abstraction, applied per-command instead of per-executor, can replace today's
inert `CommandHandle` and unify several concerns.

## The unifying idea

The client submits a `PhoneCommand` (the **input** — what to do). The server
creates a `Run` (the **entity** — the live execution being observed). A `Run`
is, all at once:

- the **receipt** (slug, phone_command, current status)
- the **producer** (executor calls `.emit(event)` as work proceeds)
- the **subscription point** (multiple consumers attach to the same event stream)

Today these are split: `CommandHandle` is a dead snapshot, `PhoneState` holds
the live record but the executor doesn't talk to it directly, and SSE
subscribers attach to a state-wide queue with no per-command targeting.

The naming distinction matters: **Command** describes work; **Run** is the
work happening. URLs reflect this — clients POST a Command to `/api/runs`
and receive a Run.

## Why this composes

A `Run` with multiple subscribers makes the topology graph trivially
extensible:

```
single mode:
  Executor ──emit──> Run ──> PhoneState mirror (for GET /api/runs/:id)
                          ├──> SSE subscriber (per UI client)
                          └──> (room for more)

server-executor mode (future):
  phone:   LocalExecutor ──emit──> Run ──> bridge-forward subscriber
                                                         │
                                                       (WS)
                                                         │
  server:  bridge-recv ──emit──> Run ──> PhoneState mirror
                                       └──> SSE subscriber
```

Going remote is "one more subscriber that forwards over a hop." No new
abstraction, just a different consumer.

## Goals

1. UI sees rich streaming progress — per-step start, step exit, daemon status
   — over the existing SSE pipe.
2. Submitting a command with a declared singleton identity (`slug`) is
   idempotent: if it's already running, return the existing run.
3. The same `Run` shape works for one-shot, daemon, and (later) remote
   execution.

## Non-goals

- Replacing SSE with WebSocket for the public API.
- Streaming raw stdout bytes over the bridge. Only **state transitions** are
  multiplexed; output bytes are still collected and reported on completion
  (or via daemon status reports for long-running ones).
- Cross-restart durability. If the server process dies, runs are lost. Disk
  persistence is a separate concern.

## Workstream A — `Run` as live handle

### Shape (sketch)

```python
class Run:
    """Live per-run handle: receipt + producer + multi-subscriber stream."""

    slug: str                       # always set; auto-gen UUID if caller didn't declare
    phone_command: PhoneCommand
    created_at: float

    @property
    def status(self) -> RunStatus: ...
    @property
    def record(self) -> RunRecord: ...    # current materialized snapshot

    def emit(self, event: RunEvent) -> None:
        """Called by the executor (or by a bridge-recv adapter)."""

    def subscribe(self) -> AsyncIterator[RunEvent]:
        """Each subscriber sees every event from subscription onward.
        Late subscribers get a synthetic 'snapshot' event first so they can
        render current state without polling."""
```

State-model rename ripple: `CommandStatus → RunStatus`, `CommandRecord → RunRecord`,
`CommandHandle` is subsumed by `Run` itself.

`RunEvent` splits into two discriminated unions:

- **`RunStateEvent`** — `created`, `step_started`, `step_exited`, `running`,
  `completed`, `failed`, `cancelled`, `daemon_started`, `daemon_status`,
  `daemon_ended`. Lifecycle deltas.
- **`RunOutputEvent`** — incremental stdout/stderr; shape defined under
  "SSE event types" below.

### Wiring

- `LocalExecutor.run(run: Run)` — replaces today's
  `submit(SubmitCommand) -> SubmitOneshotResult`. The executor's contract
  becomes: drive the run forward, emit events; do not return values. (Final
  result is just the last event; consumers either iterate or read
  `run.record`.)
- `PhoneState` keeps its `slug → RunRecord` mirror, but updates it
  by subscribing to each new run. Same with SSE: API layer subscribes to
  runs (via PhoneState meta-channel — see below) and forwards events out as
  SSE.
- `PhoneState` gains a meta-channel for "new run started / removed", so SSE
  subscribers don't have to enumerate runs at attach time.

### `SingleMain` and `PhoneState` are independent

`PhoneState` is a phone-scoped state container. `SingleMain` is one
orchestrator that holds one `PhoneState` plus a `LocalExecutor`. A future
multi-device orchestrator (working name `HubMain`) will hold many
`PhoneState`s plus the corresponding executors. Both implement
`XumretService`. They are not merged: `PhoneState` must remain reusable
across orchestrator shapes.

### Late-subscriber semantics

Late subscribers fetch `GET /api/runs/{slug}/state` for the current snapshot
(transition log + bounded output tails), then attach to SSE for live deltas
going forward. **No synthetic in-band snapshot event.** SSE carries deltas
only; the client merges (event-sourcing-style) snapshot + deltas to render
current state.

### Per-stream configuration (`StreamConfig`)

Each `ProcessStep` carries a `StreamConfig` for `stdout` and `stderr`,
declared by the client on the `PhoneCommand`:

```python
class StreamConfig(BaseModel):
    mode: Literal["lines", "binary"] = "lines"
    back_pressure: bool = False
```

`mode` controls how the executor frames reads from the fd:

- `lines` — decode bytes as UTF-8 (`errors="replace"`), split on `\n`, emit
  lines as JSON strings (no trailing newline). Natural for log-like output.
- `binary` — raw byte chunks, base64-encoded into the JSON event payload.
  Use for media, captures, or anything not safely UTF-8.

`back_pressure` controls overflow handling when downstream is slow:

- `True` — executor reads only when there is room in the subscriber queue.
  The subprocess naturally pauses on pipe buffer fill. No drops; events
  always carry data.
- `False` — executor always drains. If a subscriber queue fills, drop oldest
  output entries for that subscriber and report counts via `dropped_*`
  fields on the next event.

Stdout `StreamConfig` is honored only when the step's stdout is actually
captured (terminal step in a pipe pipeline, or a temp-file connection).
Piped-to-next stdouts ignore it. Stderr is always captured per-step.

### SSE event types

The `/events` SSE stream emits two categories of event:

1. **`run_state`** — per-run lifecycle transitions: created, step_started,
   step_exited, running, completed, failed, cancelled, daemon_started,
   daemon_status, daemon_ended. Payload includes the new status and any
   relevant metadata (pid for step_started, exit_code for step_exited,
   handle_id for daemon_*).

2. **`run_output`** — incremental stdout/stderr from a process:

   ```python
   class RunOutputEvent(BaseModel):
       slug: str
       step_index: int
       fd: Literal["stdout", "stderr"]
       # populated based on the step's StreamConfig.mode
       lines: list[str] | None = None
       bytes: str | None = None             # base64-encoded
       # populated when StreamConfig.back_pressure=False and drops occurred
       dropped_lines: int | None = None     # delta since last event for this fd
       dropped_bytes: int | None = None
   ```

   `dropped_*` fields are **deltas** (not running totals); clients can
   accumulate them if they want a cumulative figure.

The client treats the SSE stream as a delta log: it consumes both types and
maintains its own model of run state plus per-step output.

### Wire format note

JSON strings cannot carry arbitrary bytes natively (they are UTF-8 text).
SSE is line-based text. So `binary`-mode output is **base64-encoded** into
a string field; `lines`-mode output is already strings (decoded by the
executor before emission).

### Internal event delivery

Per-subscriber `asyncio.Queue`. Same primitive `PhoneState` uses today. Late
events get dropped if a queue is full (acceptable; clients are expected to
keep up or reconnect via fetch-`/state`-then-SSE).

### Cost

~300-500 LoC across `state/`, `executor/local.py`, `single.py`, `server/api/`,
plus tests. UI changes (rendering per-step progress) are incremental on top.

## Workstream B — slug as the unified process key

### Design principle: mechanism vs. policy

The **client** chooses the slug. The **server** is pure mechanism: it runs
what it's told, dedups according to declared rules, and reports state. It does
not invent identity. Auto-generation only happens as a fallback when the
client explicitly opts out by leaving `slug=None`.

### `PhoneCommand` gains a `RunOption`

```python
class RunOption(BaseModel):
    slug: str | None = None       # caller-declared identity; None → auto-gen
    mutex_by_slug: bool = False   # only meaningful when slug is set

class PhoneCommand(BaseModel):
    # ... existing fields ...
    run_option: RunOption = RunOption()
```

`RunOption` lives on `PhoneCommand` (not as a submit kwarg) so it travels with
the command across the bridge — server forwarding to a remote executor passes
one type, not two.

### Slug is the unified identifier

The slug **is** the run identifier. There is no separate `command_id` field.
Today's `command_id` everywhere — `CommandRecord.command_id`,
`SubmitCommand.command_id`, URL `/api/commands/{id}`, etc. — gets renamed
`slug` and the resource path moves to `/api/runs/{slug}`.

### Submit decision matrix

`PhoneState.submit(phone_command)` reads `run_option`:

| `slug` | `mutex_by_slug` | Live run? | Unreaped terminal? | Result                                         |
|--------|-----------------|-----------|--------------------|------------------------------------------------|
| None   | (n/a)           | n/a       | n/a                | Auto-generate UUID slug, create fresh run      |
| `"X"`  | `False`         | yes       | –                  | Return existing run's handle (idempotent join) |
| `"X"`  | `False`         | no        | yes                | **409** — client must reap the terminal first  |
| `"X"`  | `False`         | no        | no                 | Create fresh run, index `X → run`              |
| `"X"`  | `True`          | yes       | –                  | **409** — slug already running                 |
| `"X"`  | `True`          | no        | yes                | **409** — client must reap the terminal first  |
| `"X"`  | `True`          | no        | no                 | Create fresh run, index `X → run`              |

`mutex_by_slug` differs only in how live runs are treated (join vs. fail).
Unreaped terminals block submission regardless of the flag.

A run is **live** while `status in {pending, running}` and **terminal** once it
reaches `completed`, `failed`, or `cancelled` (it won't transition again).

A terminal record is a **zombie**: it persists in `PhoneState` holding the
run's result, and it occupies the slug slot. The client must explicitly
**reap** it (acknowledge the result) before a new run can be submitted under
the same slug. This mirrors POSIX `wait()` / pthread `join()` — the parent
must consume the child's exit status before the slot is released.

Both **live** and **unreaped terminal** records block a fresh submit with
the same slug. The difference is what kind of action the client takes to
unblock: cancel for live, reap for terminal.

### Where dedup happens

Dedup is a **scheduling** decision, owned by `PhoneState`. `LocalExecutor`
just runs what it's handed and emits events. The slug index lives in
`PhoneState` alongside the `slug → Run` map.

### HTTP API surface

Convention: **GET** is safe and side-effect-free; **PUT** is idempotent and
may have side effects (resource upsert); **POST** is for named actions and
is also idempotent under our convention. **DELETE is not used.** Calling any
of these twice with the same input must produce the same observable outcome.

Paths shown below are the run-scoped portion. In multi-device deployments
they prefix with the device scope from [`ui_api.md`](ui_api.md), giving e.g.
`/api/ui_v0/devices/{device_id}/runs/{slug}`. In single mode the device
prefix may be elided.

| HTTP   | Path (run-scoped portion)   | Purpose                                                |
|--------|-----------------------------|--------------------------------------------------------|
| POST   | `…/runs`                    | Submit (auto-gen slug or caller-declared)              |
| GET    | `…/runs`                    | List all records (live + unreaped terminal)            |
| GET    | `…/runs/{slug}`             | Slim record — status, error, result summary           |
| GET    | `…/runs/{slug}/state`       | Rich state — transition log + per-step output buffers |
| POST   | `…/runs/{slug}/stop`        | Cancel a live run (no-op if already terminal)         |
| POST   | `…/runs/{slug}/reap`        | Reap a terminal run (frees slug)                      |
| GET    | `…/events`                  | SSE stream of run events (existing)                   |

Idempotency notes per endpoint:

- `POST /api/runs` with the same slug + `mutex_by_slug=False` returns the
  existing run's handle on repeat calls.
- `POST /api/runs/{slug}/stop` on an already-terminal run is a successful
  no-op.
- `POST /api/runs/{slug}/reap` on an already-reaped (or never-existed) slug
  returns 404; the call has no other effects.

### Output buffering and `/state`

`GET /api/runs/{slug}/state` returns a **bounded snapshot up to now**:

- Full transition log (`step_started`, `step_exited`, status changes — these
  are small).
- Per-step stdout/stderr **tails** with a fixed cap of **128 KiB per
  process** (i.e., per pipeline step). Older bytes are dropped FIFO. The
  cap may later be configurable; for v0.2 it's a constant.

For live tailing, the client opens SSE on `/api/events` after fetching
`/state`. The `/state` snapshot is the "join point"; SSE continues from
there with `run_state` and `run_output` deltas (see SSE event types above).
This keeps `/state` cheap and bounded while still allowing unbounded live
observation.

### Cancel vs. reap

Both are POST. Both are distinct operations:

- **stop** transitions a live run to `cancelled` (a terminal status). The
  record persists, holding any output captured up to the cancellation point.
- **reap** removes a terminal record from `PhoneState`, freeing the slug.

A live-then-reaped sequence is therefore two calls: stop, then reap. Stopping
does not auto-reap because the client may want to fetch the partial result
between the two calls.

### Auto-gen slugs are reaped too

Symmetry: a slug auto-generated by the server is still owned by the client
that submitted it (the slug is returned in the submit response). The client
must reap it once the run reaches a terminal state, otherwise zombies
accumulate. Fire-and-forget callers must `submit → ... → ack` as a sequence;
no exception for auto-gen slugs.

If this proves too inconvenient in practice, a future `RunOption.auto_reap`
flag can opt specific runs into automatic reaping after their last subscriber
disconnects. Out of scope for v1.

### Zombie GC

If the client crashes or simply forgets to reap, terminal records accumulate
in `PhoneState` indefinitely. v1 has no GC: clients are responsible. Document
the risk; revisit (TTL-based reaper) only if it bites.

### Auto-generated slugs

When `slug=None`, the server generates a UUID4 — opaque, globally unique.
We do **not** derive a slug from the command tuple (argv hash). Argv-derived
identity is fragile (env, ordering, near-duplicates) and would silently
collide with caller-declared slugs in pathological cases. UUID is honest:
"this run has no logical identity beyond itself."

### Disconnect-recovery falls out as caller-driven policy

Once the bridge exists: when a remote executor reconnects, runs that didn't
survive get marked `failed` with `error="executor_lost"` after a TTL. The
controller's strategy is "re-submit by slug with `mutex_by_slug=False`":
- existing live → join (no-op)
- terminal/missing → fresh run

No dedicated `resumable_pending()` machinery. Recovery is a 3-line caller
loop on top of slug semantics.

### Cost

~150-250 LoC including tests. The bulk is the rename
(`command_id → slug`, `Command* → Run*` for state types, `/api/commands → /api/runs`
in routes and webui-src), plus index bookkeeping and conflict tests.

## What's not in this plan

**Discriminated-union dispatch on `server_bridge/`.** That was originally
listed here. It's wire-protocol plumbing for `server_bridge/ws.py`, which
doesn't exist yet, and it's not on the same semantic plane as command-lifecycle
abstractions. Fold it into bridge work when that lands; it's ~30 LoC.

## Recommended order

1. **A** (`Run` shape + executor refactor + PhoneState rewire). This
   is the foundation; B depends on it because slug indexing is a property of
   `PhoneState.submit`.
2. **B** (slug-as-singleton). Small addition once A is in place.
3. *(separately, when bridge work happens)* RemoteExecutor as another
   subscriber-style consumer; bridge wire-protocol dispatch refactor.

## Decisions (resolved 2026-05-09)

1. **Submit endpoint:** single `POST /api/runs`. Slug, if any, lives in the
   request body via `phone_command.run_option.slug`. No `PUT /…/runs/{slug}`
   variant.
2. **Output buffer cap:** **128 KiB per process** (per pipeline step). FIFO
   drop of older bytes. Constant for v0.2; configurable later.
3. **Internal event delivery:** per-subscriber `asyncio.Queue`.
4. **Late-subscriber semantics:** no in-band snapshot event. Clients fetch
   `GET /api/runs/{slug}/state` for current snapshot, then attach to SSE
   for `run_state` and `run_output` deltas. Client does the merge
   (event-sourcing-style).

## Provenance

- Source comparison: `xumret-alt/xumret/src/xumret/executor.py:32` (StateEmitter
  protocol — applied per-executor in alt; per-command here).
- Current code touched: `src/xumret/state/models.py`, `state/phone.py`,
  `executor/local.py`, `executor/models.py`, `server/api/events.py`,
  `single.py`.
