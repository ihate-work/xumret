# wits

small ideas thay might land in future. each entry should be VERY VERY concise but not losing intent or rationale / decisions.

- [ ] yyyy-mm-dd idea or thought
- [x] yyyy-mm-dd finished

- [ ] 2026-05-02 first-run-on-real-device warning: xumret is effectively an RCE / reverse shell
    — user must acknowledge the security implication before the executor starts accepting commands on an actual phone. Dev/emulator can skip.
- [ ] 2026-05-02 PhoneCommand taxonomy: archetypes, composition patterns, output lifecycle → [doc/phone-command-taxonomy.md](phone-command-taxonomy.md)
    — 5 archetypes (query/action/capture/stream/dialog), 4 topologies (pipe/tempfile/sequence/parallel), 3 output strategies (tail/spool/forward). Pseudocode PhoneCommand v2 for discussion.
- [ ] 2026-05-02 device state is a single `GET /api/ui_v0/devices/:device_id/state`
    — server OR executor polls termux-api and caches the combined state (battery, wifi, location, telephony, more) so the UI hits one endpoint. No per-sensor sub-routes.
- [ ] 2026-05-02 a command is a multi-step pipeline (each step is a subprocess). Will need API routes to fetch per-step results (stdout/stderr/exit_code) individually, not just the rolled-up command status.
- [x] 2026-05-04 Vite dev proxy targets phone-hosted `xumret single` at `http://127.0.0.1:8080` via one top-level constant
    — WebUI API contract is `/api` only; keep the host switch in one place for real-device dev.
