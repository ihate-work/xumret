---
date: 2026-05-18 11:34
branch: refactor-run-sse
host: rarity
user: mono
tldr: Made Executor an ABC; wired real device listing and per-slice state fetchers through regular PhoneCommand runs; added Makefile.var/.template plumbing with REMOTE_ADDR vite proxy injection; codified verify-after-edit and no-change-for-no-reason rules into AGENTS.md.
---

# Journal: executor ABC, device API + frontend wiring, Makefile.var, AGENTS.md rules

## Intent

A multi-thread session driven by sequential user prompts:

1. Fix the `make typecheck` error introduced after refactor-run-sse.
2. Convert `Executor` Protocol → ABC; have implementers inherit.
3. Make the frontend stop showing canned data — wire device listing + per-card state to the real backend, using regular PhoneCommands rather than dedicated endpoints.
4. Bootstrap a local-only `Makefile.var` (+ template, gitignored, required), then use it to inject `REMOTE_ADDR` into vite's dev proxy so `make webui-dev` can target a remote phone instance.
5. Codify two rules in AGENTS.md: verify after editing (typecheck/test/build), and "no change for no reason."
6. Add a `webui-prod-build` make target.

## What happened

### Executor: Protocol → ABC

`src/xumret/protocol/executor.py` flipped from `class Executor(Protocol)` to `class Executor(ABC)` with `@abstractmethod` on `run`/`stop`/`shutdown`. `LocalExecutor` and `DummyExecutor` now explicitly inherit. The earlier mypy error in `__main__.py` (LocalExecutor vs DummyExecutor branch-merge) was first fixed by adding an `executor: Executor` annotation; the ABC change preserves that.

### Device API + frontend wiring (the big chunk)

User's design constraints, given verbatim:
- Device listing: real endpoint, `id = name = hostname` (single-mode there is just one device).
- State fetch: **on-demand** with a TODO for stale-while-revalidate caching mode.
- **Do not** create dedicated `/api/devices/{id}/battery`-style endpoints — obtaining state must be a plain `PhoneCommand`.

Backend:
- New `src/xumret/protocol/device.py` with a tiny `Device(BaseModel)`.
- `XumretService` protocol gained `async def list_devices() -> list[Device]`.
- `SingleMain.list_devices()` returns `[Device(id=socket.gethostname(), name=socket.gethostname())]`.
- Route `GET /api/devices` added to `routes.py`.
- TODO comment on `RunOption` describing the stale-while-revalidate execution mode we want next (caller declares `cache_for: float`; if a recent successful run with the same slug completed within N seconds return its record; otherwise rerun; in the SWR window return cached AND kick off a background refresh).

Frontend:
- `webui-src/util/devices.ts` — `listDevices()` against `/api/devices`.
- `webui-src/pages/devices/index.tsx` rewritten to actually fetch + render loading/error states.
- `webui-src/util/commands.ts` re-synced with the real backend `PhoneCommand` shape (added `desc`, `timeout`, fixed `StreamConfig` to use `capture` instead of the never-real `back_pressure`); deprecated fields (`connections`, `daemon`) kept optional so the existing runs page still typechecks.
- `webui-src/util/deviceState.ts` is the heart of it — `runAndParse<T>` (and `runAndCaptureRaw`) submits a one-shot `PhoneCommand` with `stdout_stream.capture: true`, polls `getRun(slug)` every 200ms until terminal, then parses the run's `steps[0].stdout_tail` as JSON. Exposes typed `fetchBattery/Wifi/Location/Telephony/SmsList/Contacts/CallLog/Cameras/Clipboard/Volume`.
- `pages/devices/:deviceId/index.tsx` rewritten with a `useSlice<T>` hook + shared `<SliceBody>` so each card spins/errors/renders independently from the same template.

End-to-end smoke against the user's already-running `:8080`:
- `curl /api/devices` → `[{"id":"rarity","name":"rarity"}]`.
- POST a `termux-battery-status` PhoneCommand → completes with the canned JSON in `stdout_tail`. Round-trip verified.

### Makefile.var pattern

Three small files coordinated:
- `Makefile.var.template` (checked in): documents the convention and lists `REMOTE_ADDR`.
- `Makefile.var` (gitignored, **required** — uses bare `include`, no leading `-`): bootstrapped from template; user sets `REMOTE_ADDR` locally to point at their phone.
- `Makefile`: `include Makefile.var` at the top; `webui-dev` exports `REMOTE_ADDR='$(REMOTE_ADDR)'` before `npx vite --host`.
- Updated `.gitignore` to exclude `Makefile.var`.

Initially shipped as `-include` (soft) — user pushed back: missing config should fail loudly. Switched to bare `include` and updated the template comment to call out the deliberate hardness.

### Vite proxy + REMOTE_ADDR

`vite.config.mts` reads `process.env.REMOTE_ADDR`, prefixes `http://` if it doesn't already start with the scheme, falls back to `127.0.0.1:8080`. Logs the resolved target at startup. I'd also added `changeOrigin: true` "for safety" — user vetoed: backend has no CORS middleware (`grep -rn cors src/` empty), so it was a no-reason change. Removed.

### AGENTS.md rules

Two bullets appended to "Coding rules" in `AGENTS.md` (which CLAUDE.md symlinks to):
- **Verify after editing**: Python → `make typecheck` + `make test`; webui-src → `npx tsc` + `npm run build`. Noted that `tsconfig.json:3` already has `noEmit: true`, so `tsc` alone is typecheck-only (no need for `--noEmit`).
- **No change for no reason**: Only edit what the task requires. Don't add "just in case" config flags, defensive try/except, fallback defaults, refactors, abstractions. Cited `changeOrigin` as the concrete prompting example.

### webui-prod-build

Plain target wrapping `npm run build`, depends on `deps`.

## Discoveries / Quirks

- **`list[...]` annotation inside a class with a `list` method**: With `from __future__ import annotations`, the annotation `list[Device]` is resolved post-class-body. Once the class defines `async def list(...)`, the bare name `list` resolves to the method, not the builtin — mypy errors with "Function `list` is not valid as a type". The existing `async def list(self) -> list[RunRecord]: ...` works because at its *own* def site `list` isn't yet bound. Fix here was to put `async def list_devices` **before** `async def list` in both the `Protocol` and `SingleMain`. (Alternatives: rename `list`, or `from builtins import list as List`.)
- **Pydantic `extra='ignore'` is the v2 default**: the frontend's `PhoneCommand` had been sending `connections` and `daemon` fields that never existed on the backend; backend silently dropped them. That's why nothing visibly broke before — but it also masked the staleness. Synced `commands.ts` to the real shape.
- **RunRecord `stdout_tail` is capped at 128 KiB per fd per step** (`OUTPUT_TAIL_CAP` in `state/run.py:42`). Fine for all current state fetches; would matter for large `termux-sms-list` dumps.
- **PhoneState submit decision matrix**: re-using a slug with a terminal-unreaped previous run → 409. For "stateless" state-fetch helpers we therefore use **no slug** (uuid each time), accepting that the runs list grows. The stale-while-revalidate TODO is the principled fix.
- **User has a dev server permanently running on :8080**: spawning a parallel `python -m xumret single` in the same session is wasteful and was rejected. Saved a `feedback-dev-server` memory.

## Changes

Backend:
- `src/xumret/__main__.py` — `executor: Executor` annotation to unify the dummy/real branches.
- `src/xumret/protocol/executor.py` — Protocol → ABC.
- `src/xumret/executor/dummy_executor.py`, `src/xumret/executor/local_executor.py` — explicit `Executor` inheritance.
- `src/xumret/protocol/device.py` (new) — `Device(BaseModel)`.
- `src/xumret/protocol/service.py` — `list_devices()` on the protocol (ordered before `list`).
- `src/xumret/single.py` — implements `list_devices()` via `socket.gethostname()`.
- `src/xumret/server/api/routes.py` — `GET /api/devices`.
- `src/xumret/executor/models.py` — TODO on `RunOption` for stale-while-revalidate.

Frontend:
- `webui-src/util/devices.ts` (new) — `listDevices()`.
- `webui-src/util/deviceState.ts` (new) — typed slice fetchers + run-poll plumbing.
- `webui-src/util/commands.ts` — synced with real backend `PhoneCommand`; legacy fields optional/deprecated.
- `webui-src/pages/devices/index.tsx` — real fetch + spinner/error states.
- `webui-src/pages/devices/:deviceId/index.tsx` — per-card slices via `useSlice<T>` + `<SliceBody>`.
- `vite.config.mts` — read `REMOTE_ADDR` from env, log resolved target.

Tooling / docs:
- `Makefile` — `include Makefile.var`; `webui-dev` exports `REMOTE_ADDR`; new `webui-prod-build`.
- `Makefile.var.template` (new), `Makefile.var` (new, gitignored).
- `.gitignore` — `Makefile.var`.
- `AGENTS.md` (= CLAUDE.md) — two new bullets: "Verify after editing", "No change for no reason".

Memory:
- `feedback-dev-server.md` — don't start a parallel xumret server; user keeps one on :8080.

## Open threads

- **Stale-while-revalidate execution mode** is currently only a TODO comment on `RunOption`. Implementing it cleans up the "every render submits another fresh run" wastefulness on the device page.
- **Device page polling cadence** is one-shot on mount. If the user wants live battery / wifi / location updates, the natural extension is either client-side `setInterval` or — better — subscribing to a device-state SSE channel once such a thing exists.
- **Multi-device** (`HubMain`) is still deferred. `list_devices()` will need to enumerate from a registry rather than `gethostname()`.
- **`commands.ts` cleanup**: the deprecated `connections`/`daemon` fields are still referenced in `pages/devices/:deviceId/runs/index.tsx:157-158`. A future pass should drop them from both sides.
