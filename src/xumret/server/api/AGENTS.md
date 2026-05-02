# api

FastAPI HTTP API for the controller WebUI. Same surface in both modes — the WebUI does not know which mode is running.

## app.py

FastAPI app factory. Wires routes, SSE events, and static asset serving. Receives a `StateManager` instance via dependency injection.

## routes.py

```
POST   /api/commands          submit a command
GET    /api/commands           list commands + status
GET    /api/commands/{id}      get single command status
DELETE /api/commands/{id}      cancel a command
```

## events.py

```
GET    /api/events             SSE stream of real-time updates
```

Subscribes to `StateManager` events and streams them to the WebUI.
