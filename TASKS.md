# Xumret Implementation Tasks

Implementation plan based on `doc/protocol.md`.

## Legend

- `[ ]` - Not started
- `[~]` - In progress
- `[x]` - Complete

---

## Phase 1: Core Infrastructure

### 1.1 Shared Module (`src/xumret/shared/`)

- [x] Define all message types per protocol spec (Section 5)
  - [x] `HELLO` (client identification only, no auth for POC)
  - [x] `CMD`, `CMD_RESULT`, `CMD_ERROR`
  - [x] `PING`, `PONG`, `EVENT`
- [x] Message envelope: `type`, `seq`, `ts`, `payload` fields
- [ ] Message validation (max 1 MB, UTF-8 JSON)
- [x] Sequence number tracking utilities
- [ ] Timestamp validation (reject messages older than 30s)

### 1.2 Server Core (`src/xumret/server/`)

- [x] WebSocket server using `websockets` library
- [x] Connection handler: accept client, register, handle messages
- [x] Configuration loading (host, port)

### 1.3 Client Core (`src/xumret/client/`)

- [x] WebSocket client using `websockets` library
- [x] Connection and reconnection logic
- [x] Configuration loading (server URL, client name)

---

## Phase 2: Authentication

> **SKIPPED FOR POC** - Authentication will be added post-MVP.
> For now, clients connect directly without pairing/auth.

---

## Phase 3: Multi-Client Management

### 3.1 Client Registry (Server)

- [x] Data structure for connected clients:
  - `client_id`, `client_name`, `status`, `last_seen`, `connection`, `pending_commands`
- [x] Client name validation: `[a-z0-9-]+`, 3-32 chars
- [x] Client name uniqueness enforcement
- [ ] Max 100 clients per server

### 3.2 Command Routing

- [x] Single target: `"target": "phone-home"`
- [x] Multi-target: `"target": ["phone-home", "tablet-work"]`
- [x] Broadcast: `"target": "*"`
- [x] Route commands to correct WebSocket connections

### 3.3 Server API

- [x] REST/WebSocket API for sending commands (REPL for POC)
- [x] List connected clients endpoint
- [ ] Client status queries

---

## Phase 4: Command Execution

### 4.1 Client Command Executor

- [x] termux-api binary invocation wrapper
- [x] Argument serialization (Intent extras format)
- [x] Output capture (stdout, stderr)
- [x] Timeout handling (30s default)
- [x] Concurrent command limit (max 10)

### 4.2 Command Allowlist (Client-side)

- [ ] Config file: `~/.config/xumret/config.yaml`
- [ ] Modes: `allowlist`, `denylist`, `all`
- [ ] Blocked command returns `CMD_ERROR {error: "COMMAND_NOT_ALLOWED"}`
- [ ] `list-commands` meta-command to report allowed commands

### 4.3 Tier 1 Commands (Core)

- [ ] `battery-status` - Battery info
- [ ] `vibrate` - Vibrate device
- [ ] `torch` - Flashlight control
- [ ] `clipboard-get` / `clipboard-set` - Clipboard access
- [ ] `notification` - Show notification
- [ ] `toast` - Show toast message

### 4.4 Tier 2 Commands (Info)

- [ ] `location` - GPS location
- [ ] `wifi-connectioninfo` - WiFi status
- [ ] `telephony-deviceinfo` - Device info
- [ ] `volume` - Volume control

### 4.5 Tier 3 Commands (Communication)

- [ ] `sms-list` / `sms-send` - SMS access
- [ ] `call-log` - Call history
- [ ] `contact-list` - Contacts

### 4.6 Tier 4 Commands (Media)

- [ ] `camera-photo` - Take photo
- [ ] `camera-info` - Camera info
- [ ] `microphone-record` - Record audio
- [ ] Binary data handling (photos/recordings) - TBD: Base64 or binary frames

---

## Phase 5: Reliability

### 5.1 Keepalive

- [ ] Server sends `PING` every 30 seconds
- [x] Client responds with `PONG` within 10 seconds
- [ ] Disconnect after 2 missed pings
- [ ] Connection timeout detection

### 5.2 Reconnection (Client)

- [x] Exponential backoff: 1s, 2s, 4s, 8s, ..., max 60s
- [x] Unlimited reconnect attempts
- [x] Reset backoff after 60s stable connection
- [x] Re-send `HELLO` on reconnect

### 5.3 State Sync

- [ ] Server re-sends pending (unacknowledged) commands on client reconnect
- [ ] Pending command retention: 5 minutes max
- [ ] Fresh sequence numbers on new session

---

## Phase 6: Security Hardening

> **DEFERRED FOR POC** - Security hardening will be added post-MVP.

---

## Phase 7: Error Handling

- [ ] Error code definitions:
  - `INVALID_MESSAGE`, `UNKNOWN_COMMAND`
  - `COMMAND_NOT_ALLOWED`, `COMMAND_FAILED`, `PERMISSION_DENIED`
  - `TIMEOUT`
- [ ] Graceful error responses
- [ ] Logging infrastructure

---

## Phase 8: CLI & Configuration

### 8.1 Server CLI (`xumret-server`)

- [x] `--host`, `--port` options (existing)
- [x] `--interactive` for REPL mode
- [ ] `--config` for config file path

### 8.2 Client CLI (`xumret-client`)

- [x] `--host`, `--port` options (existing)
- [x] `--name` for client name
- [ ] `--config` for config file path

### 8.3 Configuration Files

- [ ] Server config schema (YAML)
- [ ] Client config schema (YAML)
- [ ] Example configs with documentation

---

## Phase 9: Testing

- [ ] Unit tests for message serialization/validation
- [ ] Integration tests: client-server connection
- [ ] Integration tests: command execution (mock termux-api)
- [ ] Stress tests: multiple clients, reconnection scenarios

---

## Phase 10: Documentation

- [ ] Complete `doc/server.md`
- [ ] Complete `doc/client.md`
- [ ] Update `README.md` with getting started guide
- [ ] API reference for server endpoints

---

## Open Questions (from protocol.md)

- [ ] **Binary data handling**: Base64 in JSON or separate binary WebSocket frames?
- [ ] **Push events**: Should client push unsolicited events (incoming SMS, low battery)?
