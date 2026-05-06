# api

FastAPI HTTP API for the controller WebUI. Same surface in both modes — the WebUI does not know which mode is running.

All routes depend on `XumretService` via FastAPI `Depends`. The app factory (`create_app`) stores the service on `app.state.service`.

## app.py

App factory. Takes an `XumretService`, mounts routes + events + static assets.

## routes.py

```
POST   /api/commands          submit a command  -> CommandHandle
GET    /api/commands           list commands     -> list[CommandResponse]
GET    /api/commands/{id}      get command       -> CommandResponse
DELETE /api/commands/{id}      cancel command    -> CommandResponse
```

## events.py

```
GET    /api/events             SSE stream of StateEvent updates
```
