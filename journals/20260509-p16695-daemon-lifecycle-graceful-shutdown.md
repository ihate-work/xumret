---
date: 2026-05-09 15:00
branch: compare-orphan
host: adastra.local
user: mono
tldr: Studied two Streamlit projects for daemon process patterns, compared with xumret's command model, implemented graceful shutdown via FastAPI lifespan.
---

# Journal: Daemon lifecycle & graceful shutdown

## Intent

Understand best practices for managing daemon-like (detached, long-running) child processes by studying two reference projects — `streamlit-process-manager` and `streamlit-webrtc` — then apply learnings to xumret's executor.

## What happened

### Reference study

Explored both projects in depth:

- **streamlit-process-manager**: Manages OS subprocesses across Streamlit reruns. Key patterns: file-based output spooling (not pipes), PID resurrection on restart (reconnect by PID + validate start_time + env), named "single groups" to prevent duplicate spawns, `@st.cache_resource` for singleton lifecycle.

- **streamlit-webrtc**: Manages WebRTC connections (in-process threads). Key patterns: weak references for worker lifecycle, `SessionShutdownObserver` polling thread for cleanup, `queue.Queue` + sentinel for thread communication, daemon threads that die with the process.

### Comparison with xumret

Mapped findings against `doc/phone-command-taxonomy.md` and the current `LocalExecutor` implementation. Identified three gaps:

1. **Daemon output is a black hole** — `_RunningDaemon.stdout_tails` initialized empty, never updated. Pipe buffers will fill and block child processes. (Not fixed this session — separate concern.)
2. **No lifecycle on server shutdown** — no signal handler, no lifespan hook. Daemons orphaned on Ctrl-C.
3. **No reconnection after restart** — decided this is not worth pursuing. Both reference projects run in-process and don't truly revive anything either. The "resurrection" code in process-manager is best-effort PID reconnection, not reliable revival.

### Decision: graceful shutdown only

Discussed the three layers of defense:
- Layer 1: FastAPI lifespan cleanup (graceful SIGTERM/SIGINT) — **implemented**
- Layer 2: SIGPIPE from broken pipes — already works for pipe-mode daemons
- Layer 3: Startup orphan reaper — deferred, only needed if file-spooling is adopted

### Implementation

Added graceful shutdown chain: FastAPI lifespan → `SingleMain.shutdown()` → `LocalExecutor.shutdown()`.

## Discoveries / Quirks

- Neither Streamlit project actually "revives" processes after server death. process-manager's cachefile is for surviving Streamlit reruns (same Python process, script re-executed), not server restarts. The PID reconnection is cleanup, not revival.
- For pipe-connected children, SIGPIPE handles orphan cleanup automatically — the OS kills the child when it tries to write to the broken pipe. This only fails if stdout is redirected to a file (spool mode).
- Python `__del__` is unreliable for cleanup — not guaranteed to run, especially during interpreter shutdown. Both reference projects use it as a safety net, not primary mechanism.

## Changes

- `src/xumret/executor/local.py` — Added `LocalExecutor.shutdown()`: iterates and kills all tracked daemons.
- `src/xumret/single.py` — Added `SingleMain.shutdown()`: cancels in-flight asyncio tasks, then delegates to executor.
- `src/xumret/server/api/app.py` — Added FastAPI `lifespan` context manager that calls `service.shutdown()` on teardown.
- `doc/dev.md` — Added "Graceful shutdown for child processes" guideline under Long running processes section.

### Scope clarification: composition is out of scope for these references

Confirmed that neither reference project addresses command composition (piping, sequencing, fan-out). Both are purely about lifecycle management of independent processes/threads. xumret's `phone-command-taxonomy.md` composition model (pipe, tempfile, sequence, parallel) is a distinct problem with no prior art from these two projects.

## Open threads

- **Daemon output capture** is still broken (`stdout_tails` never populated). The taxonomy doc's "spool to file" approach is the right fix but was deferred.
- **Startup orphan reaper** — only needed if/when file-spooled output is implemented. Deferred.
- **Named daemon slots** (duplicate prevention) — discussed but not implemented. Would prevent "start sensor stream" from spawning a second copy on resubmit.
- **Command composition** — needs its own reference study or design work. The two Streamlit projects offer nothing here.
