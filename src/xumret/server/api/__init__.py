"""HTTP API for the controller WebUI."""

from __future__ import annotations

from fastapi import Request

from xumret.protocol.service import XumretService


def get_service(request: Request) -> XumretService:
    return request.app.state.service
