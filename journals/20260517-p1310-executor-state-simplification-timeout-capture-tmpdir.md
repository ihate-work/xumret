---
date: 2026-05-17 14:12
branch: refactor-run-sse
host: adastra
user: mono
tldr: Six-phase simplification of `executor` and `state` packages — stripped dead daemon code, folded listeners into constructor `on_event`, introduced `RunStateTimedOut`/graceful timeout, rewrote LocalExecutor on top of ProcessGraphBuilder with capture-to-tmpdir + tee semantics. 89/89 tests pass, typecheck clean for new code.
---

# Journal: executor + state simplification (timeout, capture-to-tmpdir)

Continuation of `20260517-p8125-executor-models-redesign-process-graph-builder.md`
— this session consumed the model reshape and ProcessGraphBuilder produced
there.

## Intent

User asked: "make a plan to simplify executor and state packages". After I
proposed phases and surfaced design questions, user answered them and said
"yes please", then later "run tests / typecheck". Goal: deliver the
simplification end-to-end with green CI.

## What happened

### Plan & design calls

Surveyed both packages, flagged three categories of slack:
1. **Daemon-shaped dead code** — events (`RunStateDaemonStarted/Status/Ended`),
   `RunRecord.daemon_started/_ended`, `_apply` branches, executor reads of
   `pc.daemon`. After removing the `daemon` flag last session, all of this was
   undirected.
2. **Drop-accounting plumbing** — `RunOutputEvent.dropped_lines/dropped_bytes`
   and `StepState.stdout/stderr_dropped` had apply logic but no producer;
   only `run_test.py` exercised them by hand.
3. **`add_listener` / `remove_listener`** — used by exactly one caller
   (`PhoneState`); ripe for collapsing into a constructor callback.

User answered the gating design questions:
- **Capture semantics**: option (b) — temp file PLUS live `RunOutputEvent`. Each
  run gets its own temp dir.
- **Timeout**: clock starts at `RunStateRunning` emit, graceful (SIGTERM →
  grace → SIGKILL), terminal state is a new `RunStateTimedOut`.

### Phase execution

Worked through six phases, each green before moving on:

1. **Strip dead state** — daemon events, drop-counter fields, no-op
   `RunStateCreated` apply branch.
2. **Fold listeners** — `Run.add_listener/remove_listener` collapsed to
   `Run.__init__(... on_event=...)`. `PhoneState.submit` binds at
   construction; `reap` just deletes from the dict (no detach).
3. **Add `RunStateTimedOut`** — class + `RunStatus.timed_out` + apply branch
   + `TERMINAL_STATUSES` inclusion.
4. **Rewrite `LocalExecutor`** — now builds a `ProcessGraph` first (validation
   error → `RunStateFailed` before any spawn), creates per-run tmpdir via
   `tempfile.mkdtemp`, wires forwarding edges via `os.pipe()` between
   executor reader tasks and dst stdin, captures stream to file AND emits
   `RunOutputEvent` when `capture=True`. Timeout via `asyncio.wait(..., timeout=...)`;
   on cancel-or-timeout: SIGTERM → 0.5s grace → SIGKILL. Always uses
   `asyncio.subprocess.PIPE` for forwarded streams (uniform read path, bytes
   traverse userspace; fine for phone-control volumes).
5. **Strip `DummyExecutor`** daemon branch; honor `StreamConfig.capture` —
   only emits `RunOutputEvent` when capture is set.
6. **Update test fixtures + docs** — 5 test files (state ×2, executor ×2,
   routes ×1) + `state/AGENTS.md` and `executor/AGENTS.md`. Also fixed
   `server/api/routes.py:40` (`daemon=pc.daemon` log field → crash) to use
   `timeout=pc.run_option.timeout`.

### Test-fixture nuances

- `routes_test.py` had two tests that relied on `daemon=True` keeping the
  dummy alive long enough for "live mutex" / "reap live 409" assertions.
  Without the daemon flag, the dummy completes instantly, so the assertions
  raced. Added `_seed_live_run` helper that calls `state.submit(...)`
  directly (bypassing the executor); run stays pending forever, race gone.
- `state/run_test.py::test_dropped_counters_accumulate` and
  `state/phone_test.py::test_reap_stops_forwarding_for_that_run` deleted —
  they enshrined behavior the simplification explicitly removed.

### Tests + typecheck

89/89 pass. Typecheck pass after fixing four mypy errors all caused by the
same quirk: iterating `(("stdout", ...), ("stderr", ...))` widens the loop
variable to `str` instead of `Literal["stdout", "stderr"]`. Solution: annotate
the iteration source as `list[tuple[FdName, ...]]` before the loop.

The remaining typecheck noise is environmental (`ihate_work` lacks
`py.typed`) and pre-existing (`__main__.py:38` has branch-order type
narrowing on `executor`).

## Discoveries / Quirks

- **mypy + literal tuples**: iterating a tuple literal that mixes string
  literals doesn't preserve the Literal type for the loop variable. Either
  annotate the iteration source as a typed list, or `cast` the loop variable.
  Showed up at 4 sites; same fix each time.
- **Linter-applied annotations unmask latent errors**: a linter added `->
  None` annotations to test functions. That made mypy actually check their
  bodies, surfacing `state.get(slug)` → `Run | None` without an
  `assert is not None`. Touching a file means owning its type cleanliness.
- **Reap detach was over-engineered for one user**: removing
  `add_listener/remove_listener` means emit-after-reap now reaches phone-wide
  subscribers. In practice nothing emits after reap (terminal runs are
  immutable), so the defensive detach was paying complexity for an event
  that doesn't happen.
- **Temp dir lifecycle**: had to NOT pop `_tmpdirs[slug]` in run's finally —
  otherwise `ex.tmpdir_for(slug)` returns `None` after termination, defeating
  the whole point of durable capture.

## Changes

State package:
- `state/models.py` — removed 3 daemon event classes, 2 daemon RunRecord
  fields, 4 drop-counter fields; added `RunStateTimedOut` and
  `RunStatus.timed_out`; widened `TERMINAL_STATUSES`.
- `state/run.py` — dropped daemon fields and apply branches, no-op
  `RunStateCreated` branch, `_listeners` list + add/remove methods;
  constructor takes `on_event` callback; `_apply_output` shrunk by half.
- `state/phone.py` — `submit` passes `on_event=self._broadcast` at
  construction; `reap` no longer calls `remove_listener`.

Executor package:
- `executor/local_executor.py` — substantially rewritten. Now uses
  `ProcessGraphBuilder`, per-run `tempfile.mkdtemp`, uniform PIPE-based read
  path with tee to file + forward fd + RunOutputEvent emit, timeout via
  `asyncio.wait`, graceful term (`_terminate_gracefully`). New
  `tmpdir_for(slug)` public method.
- `executor/dummy_executor.py` — daemon branch removed; emits
  `RunOutputEvent` only when `step.stdout_stream.capture`.
- `executor/process_graph.py` — imported `StreamConfig` (was used in a type
  annotation but missing from imports); typed `streams` list to keep
  `FdName` narrowing through the iteration.

Other source:
- `server/api/routes.py` — line 40 `daemon=pc.daemon` → `timeout=...` (was a
  crash at import after the model reshape).

Tests:
- `state/run_test.py` — deleted `test_dropped_counters_accumulate`; rewrote
  two listener tests as `on_event` tests.
- `state/phone_test.py` — deleted `test_reap_stops_forwarding_for_that_run`;
  added `assert run is not None` after `state.get(...)` (linter-typed test
  unmasked the union-attr).
- `executor/local_executor_test.py` — full rewrite. New tests for dropped
  stream, forward-only, forward+capture tee, timeout-emits-timed_out,
  capture-writes-to-tmpfile, invalid-graph-fails.
- `executor/dummy_executor_test.py` — rewrite; deleted two daemon tests
  (dummy no longer has daemon behavior).
- `server/api/routes_test.py` — drop `daemon=` / `connections=` from
  `_submit`; added `_seed_live_run` helper for tests that need a non-racing
  live run.

Docs:
- `executor/AGENTS.md` and `state/AGENTS.md` — rewritten to match new shape
  (forwarding inline, capture semantics, on_event constructor, timed_out
  state, RunStateTimedOut).

## Open threads

- **Temp dir cleanup**. `_tmpdirs[slug]` entries (and on-disk dirs) leak
  until process exit. `PhoneState.reap` should drive disk cleanup;
  `LocalExecutor.shutdown` should clear both. Not done this session.
- **`__main__.py:38` typecheck error** — pre-existing. `executor` variable's
  type is narrowed to `DummyExecutor` by the first branch. Trivial fix:
  annotate `executor: Executor` (the protocol) at top.
- **`server/api/events.py:5-6`** docstring still mentions
  `daemon_started/daemon_status/daemon_ended`. Cosmetic.
- **`server_bridge/models.py:10`** docstring still mentions
  "query_daemon_status as messages". Cosmetic.
- **`doc/design-process-management.md`** (referenced from `phone.py`) may
  still describe the daemon flag. Not checked.
- **`RunOption` → `RunConfig` rename** TODO in `executor/models.py`. Defer.
