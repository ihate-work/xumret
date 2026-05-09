# api

FastAPI HTTP API for the controller WebUI. Same surface in both modes —
the WebUI does not know which mode is running.

All routes depend on `XumretService` via FastAPI `Depends`. The app factory
(`create_app`) stores the service on `app.state.service`.

Verbs: GET (safe), POST (named idempotent action). DELETE is not used.

## app.py

App factory. Takes an `XumretService`, mounts routes + events + static assets.

## routes.py

```
POST   /api/runs                submit (slug in body via run_option) -> RunRecord
GET    /api/runs                list runs                            -> [RunRecord]
GET    /api/runs/{slug}         slim record                          -> RunRecord
GET    /api/runs/{slug}/state   rich state (transitions + tails)     -> RunRecord
POST   /api/runs/{slug}/stop    cancel a live run                    -> RunRecord
POST   /api/runs/{slug}/reap    reap a terminal run                  -> {slug, reaped}
```

Conflicts surface as 409: terminal-unreaped slug or live-mutex collision
on submit; reap on a still-live slug.

## events.py

```
GET    /api/events    SSE stream
```

Two event categories:
- `event: run_state` — `RunStateEvent` payload (lifecycle deltas)
- `event: run_output` — `RunOutputEvent` payload (incremental stdout/stderr)

Late subscribers fetch `…/runs/{slug}/state` for a snapshot, then attach
here for deltas.
