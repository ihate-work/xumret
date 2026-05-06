# Scope Component Guidelines

Each directory under `components/` represents a **scope** — a domain of termux-api functionality.

The WebUI is the **policy** layer: it knows which termux commands to compose for each use case and how to interpret their results. The Python backend is pure mechanism — do not leak termux-api domain knowledge into it.

## Directory layout

```
components/
  <scope>/
    types.ts      — Response interfaces for termux-api command output
    commands.ts   — PhoneCommand factory functions to send via the API
```

## types.ts

Define interfaces matching the JSON output of each termux-api command in the scope.

Sources of truth (in priority order):

1. Java handler in `vendor/termux-api/app/src/main/java/com/termux/api/apis/`
2. CLI script in `vendor/termux-api-package/scripts/`
3. Dummy executor canned data in `src/xumret/executor/dummy_executor.py`

Conventions:

- Top-level response type: `<Command>Response` (e.g. `CameraInfoResponse`)
- Fields that map Android enum constants: use `KnownType | number` unions, because unrecognised values fall through as raw integers in the JSON
- Commands with no JSON output (binary output, fire-and-forget): document the behaviour in a trailing comment, no response type needed

## commands.ts

Import `PhoneCommand` from `~/util/commands`. Export one function per termux-api operation.

- Function name: camelCase of the operation (e.g. `cameraInfo`, `cameraPhoto`)
- Parameters: map to CLI flags, with sensible defaults where the script has them
- JSDoc: the termux command name and a one-liner
- Return: `PhoneCommand` with correct `argv`, `connections`, and `daemon` flag

Multi-step commands: populate `steps` and `connections` (one fewer connection than steps). Use `{ type: 'pipe' }` when stdout→stdin chaining is needed, `{ type: 'temp_file' }` for file-based handoff.

## Shared types

`~/util/commands.ts` defines `PhoneCommand`, `ProcessStep`, `Connection` — mirrors the Python models in `src/xumret/executor/models.py`.

## Scopes

| Scope     | Commands                                                                  |
| --------- | ------------------------------------------------------------------------- |
| camera    | termux-camera-info, termux-camera-photo                                   |
| device    | termux-battery-status, termux-location, termux-wifi-*, termux-telephony-* |
| sms       | termux-sms-list, termux-sms-send                                          |
| contacts  | termux-contact-list                                                       |
| call      | termux-call-log, termux-telephony-call                                    |
| clipboard | termux-clipboard-get, termux-clipboard-set                                |
| sound     | termux-volume, termux-media-player, termux-microphone-record              |
