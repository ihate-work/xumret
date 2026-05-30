# wits

small ideas thay might land in future. each entry should be VERY VERY concise but not losing intent or rationale / decisions.

- [ ] yyyy-mm-dd idea or thought
- [x] yyyy-mm-dd finished

- [ ] 2026-05-02 first-run-on-real-device warning: xumret is effectively an RCE / reverse shell
    — user must acknowledge the security implication before the executor starts accepting commands on an actual phone. Dev/emulator can skip.
- [ ] 2026-05-02 PhoneCommand taxonomy: archetypes, composition patterns, output lifecycle → [doc/design-command-compose.md](design-command-compose.md)
    — 5 archetypes (query/action/capture/stream/dialog), 4 topologies (pipe/tempfile/sequence/parallel), 3 output strategies (tail/spool/forward). Pseudocode PhoneCommand v2 for discussion.
- [x] 2026-05-02 device state is a single `GET /api/ui_v0/devices/:device_id/state` — superseded 2026-05-26
    — original idea: server-side aggregate endpoint. Resolved differently: per-fetcher slugged Runs with `cache_for` provide the same effect (one termux-* run per slug per N seconds, shared across UI components) without a new endpoint shape. See `webui-src/util/deviceState.ts` + [doc/design-process-management.md](design-process-management.md).
- [ ] 2026-05-02 a command is a multi-step pipeline (each step is a subprocess). Will need API routes to fetch per-step results (stdout/stderr/exit_code) individually, not just the rolled-up command status.
- [x] 2026-05-04 Vite dev proxy targets phone-hosted `xumret single` at `http://127.0.0.1:8080` via one top-level constant
    — WebUI API contract is `/api` only; keep the host switch in one place for real-device dev.
- [ ] 2026-05-09 Run as live handle; slug == identifier; reap before re-submit → [doc/design-process-management.md](design-process-management.md)
    — submit a `PhoneCommand`, observe a `Run`. Slug is client-declared (mechanism vs. policy). Live + unreaped-terminal both block fresh submit; cancel transitions to terminal, reap removes. Verbs: GET/PUT/POST only, no DELETE.
- [ ] 2026-05-22 single generic `useApi(sdkFn, args?, config?)` hook in `webui-src/_api/index.tsx`
    — replaces per-endpoint hooks AND the broken `@hey-api/openapi-ts` v0.97.1 'swr' plugin. Takes an SDK function reference; cache key is `[fn.name, args]` (no URL strings at call sites). Client injected from `ApiContext` (default = generated singleton, overridable via `<ApiProvider client={...}>` for tests/mocks). Always sets `throwOnError: true` and unwraps `.data`. `args = null` disables the fetch (SWR conditional pattern); `args` omitted is fine for no-arg endpoints.
- [x] 2026-05-23 frontend SDK folder is `webui-src/_api/`, not `webui-src/api/`
    — Vite serves files relative to its root (`webui-src/`), so an `api/` folder would be served at `/api/index.tsx` and get hijacked by the `/api` dev-proxy rule that forwards to FastAPI (→ 404). Underscore prefix dodges the collision; alias is `~/_api`.
- [ ] 2026-05-26 device-side termux stdout (`Run.steps[].stdout_tail`) is unvalidated — parsed in `webui-src/util/deviceState.ts` via `JSON.parse(...) as T`
    — Layer-1 zod validation (SDK responseValidator) covers the FastAPI contract; the JSON inside `stdout_tail` is opaque to OpenAPI. Permission denials / empty results from termux-call-log etc. can come back as objects or `null`, which the cast hides and DataTable then crashes on. Fix candidates: (a) hand-written zod schemas alongside the interfaces in `deviceState.ts`, (b) push the parsing server-side as Pydantic models so it flows through OpenAPI.
