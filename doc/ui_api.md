# UI API (draft)

Prefix: `/api/ui_v0/`

See [`runs-design.md`](runs-design.md) for the semantics behind `runs`,
slugs, and reap. This file is the route inventory; `runs-design.md` is the
source of truth for behaviour.

## Devices

```
GET    /api/ui_v0/devices
GET    /api/ui_v0/devices/:device_id
```

## Device state

```
GET    /api/ui_v0/devices/:device_id/state
```

## Runs

A run is a `PhoneCommand` being (or having been) executed. The `slug` is
the run identifier, scoped to the device. See `runs-design.md`.

```
POST   /api/ui_v0/devices/:device_id/runs                  # submit
GET    /api/ui_v0/devices/:device_id/runs                  # list
GET    /api/ui_v0/devices/:device_id/runs/:slug            # slim record
GET    /api/ui_v0/devices/:device_id/runs/:slug/state      # transitions + output buffers
POST   /api/ui_v0/devices/:device_id/runs/:slug/stop       # cancel a live run
POST   /api/ui_v0/devices/:device_id/runs/:slug/reap       # reap a terminal run
```

Verbs: GET (safe), PUT (idempotent upsert), POST (idempotent named action).
DELETE is not used.

## Events

```
GET    /api/ui_v0/devices/:device_id/events
```

SSE stream for the device. Two event categories:

- `event: run_state` — per-run lifecycle deltas (created, step_started,
  step_exited, running, completed, failed, cancelled, daemon_*).
- `event: run_output` — incremental stdout/stderr chunks per process:
  `{slug, step_index, stream, offset, bytes}`.

Late subscribers fetch `…/runs/:slug/state` for a current snapshot, then
attach to SSE for deltas. The client merges snapshot + deltas
event-sourcing-style; no in-band snapshot event is sent.
