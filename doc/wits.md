# wits

small ideas thay might land in future. each entry should be VERY VERY concise but not losing intent or rationale / decisions.

- [ ] yyyy-mm-dd idea or thought
- [x] yyyy-mm-dd finished

- [ ] 2026-05-02 first-run-on-real-device warning: xumret is effectively an RCE / reverse shell
    — user must acknowledge the security implication before the executor starts accepting commands on an actual phone. Dev/emulator can skip.
- [ ] 2026-05-02 PhoneCommand taxonomy: archetypes, composition patterns, output lifecycle → [doc/design-command-compose.md](design-command-compose.md)
    — 5 archetypes (query/action/capture/stream/dialog), 4 topologies (pipe/tempfile/sequence/parallel), 3 output strategies (tail/spool/forward). Pseudocode PhoneCommand v2 for discussion.
- [ ] 2026-05-02 device state is a single `GET /api/ui_v0/devices/:device_id/state`
    — server OR executor polls termux-api and caches the combined state (battery, wifi, location, telephony, more) so the UI hits one endpoint. No per-sensor sub-routes.
- [ ] 2026-05-02 a command is a multi-step pipeline (each step is a subprocess). Will need API routes to fetch per-step results (stdout/stderr/exit_code) individually, not just the rolled-up command status.
- [x] 2026-05-04 Vite dev proxy targets phone-hosted `xumret single` at `http://127.0.0.1:8080` via one top-level constant
    — WebUI API contract is `/api` only; keep the host switch in one place for real-device dev.
- [ ] 2026-05-09 Run as live handle; slug == identifier; reap before re-submit → [doc/design-process-management.md](design-process-management.md)
    — submit a `PhoneCommand`, observe a `Run`. Slug is client-declared (mechanism vs. policy). Live + unreaped-terminal both block fresh submit; cancel transitions to terminal, reap removes. Verbs: GET/PUT/POST only, no DELETE.
- [ ] 2026-05-22 single generic `useApi(sdkFn, args?, config?)` hook in `webui-src/api/index.tsx`
    — replaces per-endpoint hooks AND the broken `@hey-api/openapi-ts` v0.97.1 'swr' plugin. Takes an SDK function reference; cache key is `[fn.name, args]` (no URL strings at call sites). Client injected from `ApiContext` (default = generated singleton, overridable via `<ApiProvider client={...}>` for tests/mocks). Always sets `throwOnError: true` and unwraps `.data`. `args = null` disables the fetch (SWR conditional pattern); `args` omitted is fine for no-arg endpoints.
