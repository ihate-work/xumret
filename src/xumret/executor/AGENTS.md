# executor

Drives Runs forward by emitting events.

## models.py

`PhoneCommand` defines a pipeline of `ProcessStep`s connected by typed
`Connection`s (`Pipe` for stdout->stdin, `TempFile` for file-based handoff).

Each `ProcessStep` carries `argv` plus `stdout_stream` and `stderr_stream`
(`StreamConfig(mode="lines"|"binary", back_pressure=False)`).

`PhoneCommand.run_option: RunOption(slug, mutex_by_slug)` — caller-declared
identity and dedup policy.

`daemon` flag toggles lifecycle: oneshot ends on last step's exit;
daemons emit `daemon_started` / `daemon_ended` and only terminate on stop.

The `Executor` protocol lives in `xumret.protocol.executor`. Single mode
talks to `LocalExecutor`; bridge work (deferred) will plug `RemoteExecutor`
behind the same shape.

## local.py

`LocalExecutor` — implements `Executor` by spawning subprocesses. Per-fd
async reader tasks honor `StreamConfig.mode`; per-step `step_started` /
`step_exited` events emitted in order; cancellation kills procs and emits
`cancelled`.

## dummy_executor.py

`DummyExecutor` — emits canned events without spawning processes. Used in
`xumret single --dummy` and tests.
