# Roadmap

## FUTURE

- contribute to termux-api itself, about camera / streaming

## NEXT: v0.2.0

- impl some typical use cases, centered with termux-api
- real executor patterns
    - one-shot
    - daemon
    - single process
    - pipe-composed processes

### Design

- [design-process-management.md](design-process-management.md) — Run abstraction, slug-keyed lifecycle,
  reap semantics, HTTP API surface. Source of truth for v0.2 subprocess
  management work.

### Tasks

- [x] study other projects (`xumret-alt` comparison; ideas folded into
  [design-process-management.md](design-process-management.md))
- [~] refine subprocess management : internal & API —
  full checklist in [task-v0.2.0-runs.md](task-v0.2.0-runs.md)
    - [x] design — [design-process-management.md](design-process-management.md)
    - [x] open decisions resolved (submit endpoint, output cap, event
      delivery, late-subscriber semantics)
    - [ ] A. `Run` as live handle (executor refactor + PhoneState rewire +
      `Command* → Run*` rename)
    - [ ] B. Slug + `RunOption` + reap
    - [ ] C. HTTP API migration to `/api/runs` (+ `/state`, `/stop`,
      `/reap`; remove DELETE)
    - [ ] D. WebUI adaptation (event-sourcing client; per-step progress
      rendering)
- [ ] reflect command patterns / composibility


## DONE: v0.1.0

- goal and architecture clear
- runs with dummy data in real phone
- published to pypi
