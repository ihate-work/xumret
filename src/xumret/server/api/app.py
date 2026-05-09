"""FastAPI app factory for xumret."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
import ihate_work.o11y as o11y

from xumret.server.api import events, routes
from xumret.protocol.service import XumretService

logger, *_ = o11y.get_o11y(__name__)

WEBUI_DIR = Path(__file__).resolve().parents[4] / "webui-assets"


def create_app(*, service: XumretService) -> FastAPI:

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        logger.info("server shutting down, cleaning up")
        if hasattr(service, "shutdown"):
            await service.shutdown()

    app = FastAPI(title="xumret", version="0.1.0", lifespan=lifespan)
    app.state.service = service

    app.include_router(routes.router)
    app.include_router(events.router)

    if WEBUI_DIR.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(WEBUI_DIR), html=True), name="webui")

    return app
