# PhoneCommand Taxonomy

Design discussion: how subprocesses compose, how their outputs persist and are reaped.

Status: **draft for discussion** — not a spec yet.

## 1. Command archetypes (by termux-api behaviour)

| Archetype | Output | Duration | Examples |
|-----------|--------|----------|----------|
| **query** | JSON/text to stdout | instant (<2s) | `termux-battery-status`, `termux-sms-list`, `termux-wifi-connectioninfo` |
| **action** | minimal/no stdout | instant | `termux-vibrate`, `termux-torch`, `termux-toast`, `termux-sms-send` |
| **capture** | binary to file path | seconds | `termux-camera-photo -c 0 /tmp/p.jpg`, `termux-microphone-record -f /tmp/r.m4a` |
| **stream** | continuous stdout until killed | unbounded | `termux-sensor -s accelerometer -d 100`, `termux-location -p gps` (in watch mode) |
| **dialog** | JSON after user interaction | user-paced | `termux-dialog -t "Pick one" -i "a,b,c"` |

Every termux-api call falls into one of these. General-purpose commands (`jq`, `grep`, `cat`, `base64`) also appear as pipeline glue and follow query or stream patterns.

## 2. Composition patterns

### 2a. Pipe

Stdout of step N → stdin of step N+1. Classic Unix pipeline.

```
termux-sms-list | jq '[.[] | {from: .number, body: .body}]'
```

Works for: query→query, query→action-with-stdin. Does NOT work for binary output or file-based capture.

### 2b. TempFile

Step N writes to a known path; step N+1 reads it. The path is the connection.

```
termux-camera-photo -c 0 /tmp/photo.jpg    # step 0: capture → file
termux-share -a send /tmp/photo.jpg         # step 1: reads that file
```

Works for: capture→anything, any step that produces a side-effect file. Requires the path to be wired into argv (template variable or convention).

### 2c. Fan-out (parallel, independent)

Multiple steps run concurrently with no connection between them. Results collected independently.

```
parallel:
  termux-battery-status        # → JSON
  termux-wifi-connectioninfo   # → JSON
  termux-location              # → JSON
```

Not a pipeline — a **batch**. Each step has its own stdout/stderr. The command result is a list of independent per-step results.

### 2d. Sequence (ordered, no data flow)

Steps run one after another. No pipe or file connection. Step N+1 starts after step N exits.

```
termux-torch on        # step 0
sleep 2                # step 1
termux-torch off       # step 2
```

The "connection" is just ordering. Optionally gated on exit code of previous step (stop-on-failure or continue-always).

### 2e. Conditional (not yet needed?)

Step B runs only if step A exits 0 (or non-zero). Shell `&&` / `||` semantics. Could be modelled as a Sequence with a `gate` field, but probably overkill for v1.

## 3. Output lifecycle

Every process produces three things: **exit_code**, **stdout bytes**, **stderr bytes**. But how we collect and expose them differs by archetype.

### 3a. One-shot (query, action, capture)

Process exits on its own. Full stdout/stderr collected via `communicate()`. Stored in `ProcessResult`. Immediately available in `PhoneCommandResult`.

```
spawn → communicate() → ProcessResult(exit_code, stdout, stderr)
```

For **capture** commands, the "real" output is a file on disk, not stdout. Stdout may be empty or a confirmation message. The file path is known from argv and could be surfaced explicitly.

### 3b. Stream / daemon

Process runs until killed. Output is unbounded. Cannot `communicate()` until process ends.

**Tail model** (current): keep a rolling buffer of the last N bytes per fd. Queryable while running. Full final output collected on `end_daemon()`.

**Problem**: the tail model loses history. For streams (sensor data, logs), the caller may want the full output, or want it written to a file.

**Possible approaches:**

| Approach | How it works | Tradeoff |
|----------|-------------|----------|
| **tail** (current) | ring buffer, last N bytes | simple; loses history |
| **spool to file** | redirect to a temp file, serve it back | preserves all; disk usage |
| **forward to callback** | each line/chunk pushed to a handler (SSE, WS, write to DB) | real-time; complex |
| **hybrid** | spool to file + tail buffer for quick queries | best of both; two codepaths |

### 3c. Reaping

When is output cleaned up?

- One-shot: output lives in `PhoneCommandResult` → sent to PhoneState → served to API → GC'd when CommandRecord is dropped.
- Daemon: tail buffers live in `_RunningDaemon` → dropped on `end_daemon()`. If spooled to file, file must be deleted explicitly.
- TempFile connections: the intermediate file must be cleaned up after the pipeline finishes (or on cancel).

## 4. Proposed pseudocode

```python
# --- Composition topology ---

class ProcessStep(BaseModel):
    argv: list[str]
    # optional: working_dir, env overrides, timeout per-step

class Pipe(BaseModel):
    """stdout(N) → stdin(N+1)"""
    type: Literal["pipe"] = "pipe"

class TempFile(BaseModel):
    """step N writes to path; step N+1 reads it.
    The path may be injected into argv via a template variable."""
    type: Literal["temp_file"] = "temp_file"
    path_template: str = ""  # e.g. "/tmp/xumret-{command_id}-{step}.dat"

class Sequence(BaseModel):
    """step N+1 starts after step N exits. No data flow."""
    type: Literal["sequence"] = "sequence"
    stop_on_failure: bool = True  # abort remaining steps if exit_code != 0

class NoConnection(BaseModel):
    """Fan-out: steps run in parallel, independent."""
    type: Literal["parallel"] = "parallel"

Connection = Pipe | TempFile | Sequence | NoConnection


# --- Lifecycle mode ---

class OneshotMode(BaseModel):
    """Run all steps, wait, return full results."""
    type: Literal["oneshot"] = "oneshot"
    timeout: float | None = None  # per-command timeout

class DaemonMode(BaseModel):
    """Start steps, return handle. Caller queries/ends later."""
    type: Literal["daemon"] = "daemon"
    output_policy: Literal["tail", "spool", "forward"] = "tail"
    tail_bytes: int = 8192


# --- PhoneCommand v2 ---

class PhoneCommand(BaseModel):
    name: str
    steps: list[ProcessStep]
    connections: list[Connection]      # len == len(steps) - 1
    mode: OneshotMode | DaemonMode = OneshotMode()


# --- Results ---

class ProcessResult(BaseModel):
    step_index: int
    exit_code: int
    stdout: str
    stderr: str
    output_file: str | None = None  # set if step produced a file (capture archetype)
    duration_ms: int | None = None

class PhoneCommandResult(BaseModel):
    command_id: str
    steps: list[ProcessResult]
    # all steps present even for fan-out; ordered by step_index


class DaemonProcessStatus(BaseModel):
    step_index: int
    running: bool
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    spool_path: str | None = None   # if output_policy == "spool"
    bytes_written: int = 0          # total output seen so far

class DaemonStatus(BaseModel):
    handle_id: str
    steps: list[DaemonProcessStatus]
    all_running: bool
```

## 5. Execution semantics per topology

```
Pipe:       spawn all at once, wire fds. Wait for all (oneshot) or run until killed (daemon).
            If any step crashes, downstream steps get EOF on stdin.

TempFile:   spawn step N, wait for exit, then spawn step N+1 with path resolved.
            Clean up temp files after command completes or on cancel.

Sequence:   spawn step N, wait for exit.
            If stop_on_failure and exit != 0: skip remaining, report partial results.
            Else: proceed to step N+1.

Parallel:   spawn all steps concurrently. Each has independent stdout/stderr.
            Wait for all (oneshot) or manage independently (daemon).
            No connection between them — like N independent commands grouped.
```

## 6. Open questions

- **TempFile path ownership**: who creates/deletes the temp file? Executor knows nothing about termux-api semantics. Possibly the WebUI (policy layer) provides the full argv including paths, and executor just cleans `/tmp/xumret-*` on completion.
- **Parallel + daemon**: does it make sense? Each step would be independently queryable. Might be better modelled as N separate commands grouped by a "batch_id".
- **Stream backpressure**: if a sensor stream produces 100 lines/sec and nobody reads, the spool file grows unbounded. Need a size cap or rotation.
- **Binary output**: `ProcessResult.stdout` is str. Capture commands produce binary files, not stdout. Should we have a `ProcessResult.output_bytes: bytes | None` or always go through files?
- **Error propagation**: in a Pipe topology, if step 1 of 3 fails, steps 2-3 get EOF. Should the command status be "failed" or "completed with errors"? Current model returns per-step exit codes, which is sufficient, but the rolled-up status needs a policy.
- **Timeout granularity**: per-step vs per-command? A 60s command timeout works for 3 quick steps but not for `termux-location` which can take 30s alone.
