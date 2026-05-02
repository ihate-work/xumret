"""FastAPI app factory for xumret server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from xumret.server.api import events, routes
from xumret.state.manager import StateManager

# WebUI static assets (built output from xumret-controller)
WEBUI_DIR = Path(__file__).resolve().parents[3] / "xumret-controller" / "dist"


def create_app(*, state_manager: StateManager) -> FastAPI:
    app = FastAPI(title="xumret", version="0.1.0")

    # Wire state into route modules
    routes.init(state_manager)
    events.init(state_manager)

    app.include_router(routes.router)
    app.include_router(events.router)

    # Serve WebUI static assets if the build exists
    if WEBUI_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")

    return app
