# Architecture

## Terms

### server

- typically runs in an internet server, exposing HTTP and WS endpoints.
- handle client sessions (session = WS connection)
- forward messages between phones and controllers
- cut bound controller sessions when phone session ended
- code: xumret.server python package

### phone or phone client

(effecitvely a reverse shell to run termux-api commands)

- connects to server via WS
- on session start, register itself to server
- handle incoming messages and reply to server
- run instructed commands
  - most of the commands starts subprocesses, one-shot or long-live
- reply message b results to server
- code: xumret.phone python package

### controller or controller client

- connects to server via WS
- on session start, register itself to server, and bind to a phone client session
- after bound to a phone session, send messages to the session and present the response via UI
- provide interactive UI
- code: xumret-controller (TypeScript+React+Rxjs components, the official web UI impl)

## Messages

Messages are categorized into:

- c2s (controller to server)
- c2p (controller to phone, the major use cases)
- s2p, s2c (heartbeat and status collector)

(almost all termux-api use cases are originated by a controller)

Messages definitions and designed are in xumret.messages python package.
