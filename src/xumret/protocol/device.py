"""Device — a phone known to xumret.

In single mode there's exactly one device (the host running the server); a
future hub mode will have many. `id` is the stable identifier the UI uses in
URLs; `name` is the human-readable label.
"""

from __future__ import annotations

from pydantic import BaseModel


class Device(BaseModel):
    id: str
    name: str
