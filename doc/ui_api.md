# WebUI ↔ API

How the FastAPI surface, the OpenAPI spec, the generated TypeScript SDK, and
the React hooks fit together.

## The pipeline

```
FastAPI routes (src/xumret/server/api/)
        │  `make openapi`  (venv/bin/python -m xumret dev-openapi)
        ▼
webui-src/_api/openapi.yaml          ← committed; source of truth
        │  npm run generate:api  (@hey-api/openapi-ts)
        ▼
webui-src/_api/generated/            ← committed; do NOT import from directly
  ├── sdk.gen.ts                    typed fetch wrappers per operation
  ├── types.gen.ts                  request/response data types
  ├── zod.gen.ts                    runtime schemas (`zDevice`, `zRunRecord`, …)
  ├── client.gen.ts + client/       fetch client + helpers
  └── index.ts                      barrel (re-exported from ../index.tsx)
        │
        ▼
webui-src/_api/index.tsx             ← public surface
  • re-exports * from ./generated and ./events
  • exposes useApi, useRunEvents, ApiProvider
        │
        ▼
webui-src/pages/**, webui-src/util/**   ← consumers import from '~/_api' only
```

`make openapi` runs both stages (regen YAML + regen SDK). CI typechecks the
result via `npm run typecheck` in `.github/workflows/check.yaml`.

## Adding or changing an endpoint

1. Edit the FastAPI route / Pydantic model.
2. Run `make openapi`. Both `webui-src/_api/openapi.yaml` and
   `webui-src/_api/generated/**` are regenerated and meant to be committed.
3. Use the new function/type from `~/_api` in components.

No manual edits to anything under `webui-src/_api/generated/`.

## Generator config

`openapi-ts.config.ts` at repo root. Plugins:

- `@hey-api/typescript` — types
- `@hey-api/sdk` with `operations: { strategy: 'flat' }` — tree-shakable
  standalone functions (no class containers)
- `@hey-api/client-fetch` — fetch-based runtime
- `zod` — runtime schemas

Plugin defaults are dropped when `plugins:` is set explicitly, so the
typescript and sdk plugins must stay in the list even though they'd be
default if omitted.

A 14-day npm cooldown (`min-release-age=14` in `~/.npmrc`) caps how new the
generator versions can be — same supply-chain posture as the Python deps.

## Frontend hooks

### `useApi(fn, args?, config?)`

Generic SWR-backed hook. Pass an SDK function and the args bag; the hook
injects the client, sets `throwOnError: true`, and unwraps `.data`. Cache key
is `[fn.name, args]` — endpoint identity comes from the function reference,
not from URL strings at the call site.

```tsx
const { data } = useApi(listDevicesApiDevicesGet);
const { data } = useApi(getRunApiRunsSlugGet, { path: { slug } });
const { data } = useApi(getRunApiRunsSlugGet, slug ? { path: { slug } } : null);
//                                            ^ null disables the fetch
```

`args` mirrors the SDK function's parameter shape (path / query / body /
headers), minus `client` and `throwOnError` which the hook owns.

### `useRunEvents(onState)`

Subscribes to `/api/events` (SSE) for the lifetime of the component and
calls `onState` on every `run_state` event. The latest callback is always
invoked — the EventSource isn't re-opened when the callback identity
changes. Typical pattern: revalidate a `useApi` result via `mutate()`.

```tsx
const { data: run, mutate } = useApi(getRunStateApiRunsSlugStateGet, { path: { slug } });
useRunEvents((ev) => { if (ev.slug === slug) mutate(); });
```

SSE isn't covered by the SDK (the Hey API generator can't model event
streams) — `webui-src/_api/events.ts` is the hand-written wrapper.

### Mutations (POST / PUT)

Call SDK functions directly from event handlers. SWR's `mutate()` from a
prior `useApi` result invalidates the cache after a mutation:

```ts
await stopRunApiRunsSlugStopPost({ path: { slug }, throwOnError: true });
await mutate();
```

For error inspection (e.g., distinguishing HTTP 409 conflict), drop
`throwOnError: true` and read `result.response.status` / `result.error`.

### `<ApiProvider client={...}>`

Optional. Overrides the client used by `useApi` within a subtree — useful
for tests, mocks, or alternate base URLs. Without it, `useApi` falls back
to the generated singleton at `webui-src/_api/generated/client.gen.ts`.

## Zod schemas

Every type has a matching `z*` schema in `webui-src/_api/generated/zod.gen.ts`
(re-exported from `~/_api`). Use them for runtime validation:

```ts
import { zRunRecord } from '~/_api';
const parsed = zRunRecord.safeParse(payload);
```

The SDK does not auto-validate. To enable, set `validator: { response: 'zod' }`
on `@hey-api/sdk` in `openapi-ts.config.ts`.

## Known gaps

- **SSE typing.** `run_state` event payloads are typed as the union of
  `RunState*` records from the spec. `run_output` (per-step stdout/stderr
  deltas) is emitted by the server but not in the OpenAPI spec, so it's
  not consumed by the WebUI. Add to the Pydantic models + regen to wire it.
- **SWR plugin.** The `@hey-api/openapi-ts` `'swr'` plugin (v0.97.1) emits
  `import type useSWR` and drops path params. We hand-wrote `useApi`
  instead. Revisit once a fixed version (≥0.97.2) clears the 14-day npm
  cooldown — see `doc/wits.md`.
