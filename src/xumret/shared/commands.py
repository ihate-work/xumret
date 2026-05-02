from typing import Any

from pydantic import BaseModel


class CommandSpec(BaseModel):
    """Base command model."""

    name: str  # binary name in termux-api
    description: str
    parameters: dict[str, Any]


X: dict[str, CommandSpec] = {
    "camera-photo": CommandSpec(
        name="termux-camera-photo",
        description="Take a photo with the camera",
        parameters={
            "filename": "The filename to save the photo to",
        },
    ),
}
