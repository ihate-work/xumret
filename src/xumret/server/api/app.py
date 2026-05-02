"""FastAPI app factory for xumret."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from xumret.server.api import events, routes
from xumret.protocol.service import XumretService

WEBUI_DIR = Path(__file__).resolve().parents[4] / "xumret-controller" / "dist"


def create_app(*, service: XumretService) -> FastAPI:
    app = FastAPI(title="xumret", version="0.1.0")
    app.state.service = service

    app.include_router(routes.router)
    app.include_router(events.router)

    if WEBUI_DIR.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")

    return app
