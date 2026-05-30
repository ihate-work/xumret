# executor

Drives Runs forward by emitting events.

## models.py

`PhoneCommand` defines a pipeline of `CommandStep`s. Forwarding between steps
is expressed inline on each step's `StreamConfig.forward_dest_process_idx`;
there is no separate connections list.

Each `CommandStep` carries `argv` plus `stdout_stream` and `stderr_stream`
(`StreamConfig(mode="lines"|"binary", capture=False, forward_dest_process_idx=None)`).
A stream that is neither captured nor forwarded is implicitly dropped.

`PhoneCommand.run_option: RunOption(timeout, slug, mutex_by_slug)` — caller
runtime policy. `timeout=None + mutex_by_slug=True` is the daemon-shape
heuristic used by the frontend; the backend does not model daemons separately.

The `Executor` protocol lives in `xumret.protocol.executor`. Single mode talks
to `LocalExecutor`; bridge work (deferred) will plug `RemoteExecutor` behind
the same shape.

## process_graph.py

`ProcessGraphBuilder` validates a `PhoneCommand` and produces a `ProcessGraph`
— a flat plan describing per-step stdin source, capture flag, and forward
edge. Validation rejects empty argv, out-of-range / self-loop / colliding
forwards, cycles in the forward graph, mutex without slug, and non-positive
timeout.

## local_executor.py

`LocalExecutor` implements `Executor` by spawning subprocesses. Builds a
`ProcessGraph` first; on validation error the run fails before any spawn.
Captured streams are tee'd into per-run temp files (path via
`tmpdir_for(slug)`) and emitted as `RunOutputEvent`s. Forwarded streams flow
through executor reader tasks (also into the temp file if also captured).
`RunOption.timeout` is enforced as a wall-clock bound from `RunStateRunning`;
expiry triggers SIGTERM → grace → SIGKILL and emits `timed_out`.

## dummy_executor.py

`DummyExecutor` emits canned events without spawning processes. Used in
`xumret single --dummy` and tests. Honors `StreamConfig.capture`; ignores
forwarding (no real pipes).
