---
date: 2026-05-17 00:51
branch: refactor-run-sse
host: adastra
user: mono
tldr: Reshaped `executor/models.py` (forwarding inline on StreamConfig, daemon→timeout, drop CommandStep rename, removed Connection/Pipe/connections) and introduced `ProcessGraphBuilder` to validate PhoneCommands and produce ready-to-spawn plans. Downstream executor + tests intentionally left stale.
---

# Journal: executor models reshape + ProcessGraphBuilder

## Intent

User had been mid-edit on `src/xumret/executor/models.py` and asked me to catch up
on the inline changes, then iteratively reshape the models toward a more expressive
shape — culminating in a new `ProcessGraphBuilder` that the executor will eventually
consume.

## What happened

### Round 1 — catching up on the in-progress edit

Reviewed the unstaged diff. User had:
- Started expanding `StreamConfig` from `(mode, back_pressure)` into a richer policy
  with `drop`, `capture`, `back_pressure_mode/buffer_size`, and
  `forward_dest_process_idx` (moving piping inline onto streams).
- Added a TODO to remove `connections: list[Connection]` from `PhoneCommand`.
- Moved `daemon` from `PhoneCommand` onto `RunOption`.
- Added `desc` to `PhoneCommand`.
- Left a truncated `# m` comment and various TODOs.

I flagged: truncated comment, `TempFile` has no inline equivalent, no mutual-exclusion
between drop/capture/forward, `forward_dest_process_idx` being a sibling-list index
(fragile under reordering), `desc: str` no default breaks callers, plus the question
of whether daemon-ness belongs on RunOption.

### Round 2 — user's design calls

User decided:
- Drop the temp-file-as-connection idea entirely (incomplete without more investment).
- Remove `back_pressure_mode` (and `buffer_size`).
- `capture` semantics change: executor captures to a **temp file** on disk, never into
  memory.
- Index-based forwarding is fine; executor validates the graph.
- `drop` becomes implicit (a stream that is neither captured nor forwarded is dropped).
- `desc: str | None`.
- Daemon flag: open question.

Made the corresponding edits in `models.py`.

### Round 3 — daemon → timeout

I framed the daemon question as "intrinsic to the command vs. caller policy" and
proposed daemon as intrinsic. User rejected the framing: **daemon-ness is observed
behavior, not a backend declaration**. Replace `daemon: bool` with
`timeout: float | None` on `RunOption`. Frontend infers the daemon UI affordance from
the heuristic `mutex_by_slug=True AND timeout is None`.

Updated `RunOption.daemon` → `RunOption.timeout` and rewrote the module docstring to
remove the daemon=True/False lifecycle split (lifecycle is now uniform; timeout just
bounds runtime).

### Round 4 — Connection/Pipe/connections removal

User asked "Connection can be removed right?" I grepped downstream first and found the
removal touches `local_executor.py:204-216` (the pipe-wiring loop) plus 5 test files.
User said "forget the downstreams, we are reshaping" — so I cut `Pipe`,
`Connection`, and `PhoneCommand.connections` from `models.py` only.

### Round 5 — ProcessStep → CommandStep

One-line rename, plus dropped the TODO comment that requested it.

### Round 6 — ProcessGraphBuilder

User asked for a new `ProcessGraphBuilder` in the executor package that **validates** a
`PhoneCommand` and **prepares** lower-level calls without executing them. The executor
will consume it later.

Designed:

- `process_graph.py` with `GraphValidationError`, `StdinSource`, `FdPlan`, `StepPlan`,
  `ProcessGraph`, `ProcessGraphBuilder`.
- Validation rules: ≥1 step, non-empty argv per step, `forward_dest_process_idx` in
  range, no self-loops, at most one inbound forward per step's stdin, no cycles
  (Kahn's algorithm), `mutex_by_slug` requires a slug, `timeout > 0` if set.
- The plan flattens each step into `stdin_from` (where stdin comes from, if anywhere)
  and per-fd `FdPlan(mode, capture, forward_to)`. `capture` and `forward_to` are
  orthogonal — both set means the executor tees; both unset means drop. This avoids
  introducing a tagged-union sink type.
- Builder is stateless: single `build(pc) -> ProcessGraph` method.

`process_graph_test.py`: 14 tests covering happy paths (single-step, linear pipeline,
stderr forwarding, capture+forward coexistence, RunOption propagation, defaulted
drop) and every validation rule. All pass.

## Discoveries / Quirks

- `os.pipe()`-based wiring in `local_executor.py:200-238` is structurally tied to the
  old `connections` list (`pc.connections[i-1]` / `pc.connections[i]` adjacency
  walks). New model needs a different wiring loop — build inbound/outbound fds from
  `forward_dest_process_idx` per step, allowing non-linear graphs.
- `local_executor.py:250` has a TODO referencing the removed `back_pressure` field —
  stale.
- `executor/AGENTS.md` is stale: still describes `Connection`/`TempFile`,
  `back_pressure`, and the daemon flag.
- User strongly prefers behavioral framing over taxonomic framing — pushed back on my
  "is daemon intrinsic or policy?" question, preferring to delete the concept and let
  emergent properties (`timeout=None + mutex_by_slug`) define it.

## Changes

- **`src/xumret/executor/models.py`** — reshaped:
  - `StreamConfig`: now `(mode, capture, forward_dest_process_idx)`; drop is implicit;
    back-pressure fields gone; capture documented as temp-file-backed.
  - `Pipe`, `Connection`, `PhoneCommand.connections` removed.
  - `TempFile` removed.
  - `RunOption`: `daemon: bool` replaced by `timeout: float | None`. Comment notes the
    daemon UI heuristic.
  - `PhoneCommand.desc: str | None = None` added.
  - `ProcessStep` renamed to `CommandStep`; docstring shortened.
  - Module docstring rewritten — uniform lifecycle, no daemon split.
- **`src/xumret/executor/process_graph.py`** — new. `ProcessGraphBuilder` + plan
  models + `GraphValidationError`.
- **`src/xumret/executor/process_graph_test.py`** — new. 14 pytest tests, all passing.

## Open threads

- **`local_executor.py` needs a rewrite** to consume `ProcessGraph` instead of walking
  `pc.connections`. Pipe wiring becomes per-edge: for each forwarding edge create an
  `os.pipe()`, hand the write-end to src step's stdout/stderr and the read-end to dst
  step's stdin. Capture (temp-file) and the both-forward-and-capture tee case need
  implementing.
- **5 downstream test files** still construct `PhoneCommand(connections=[...])` and/or
  `daemon=...`; they will fail to import / instantiate.
  - `src/xumret/executor/local_executor_test.py`
  - `src/xumret/executor/dummy_executor_test.py`
  - `src/xumret/server/api/routes_test.py`
  - `src/xumret/state/run_test.py`
  - `src/xumret/state/phone_test.py`
- `dummy_executor.py` likely references the old shape too (not grepped this session).
- **AGENTS.md** in `executor/` is stale — references `Connection`/`TempFile`/
  `back_pressure`/`daemon`. Should be rewritten when the executor catches up.
- **TODO in `RunOption`**: "rename to RunConfig" — not done this session.
- **Spawn order**: builder doesn't emit a topological order; spawn order doesn't
  matter for `os.pipe()` (pipes can be created up front), but the executor rewrite
  should confirm this assumption.
- **Tee implementation strategy**: for `capture=True AND forward_to=X`, the executor
  needs to read from the process pipe and fan out to both a temp file and the next
  step's stdin. Not designed yet.
