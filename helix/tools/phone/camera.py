"""Camera tool — take photos via Termux:API."""
from __future__ import annotations

import base64, os
from pathlib import Path

from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneCameraPhoto(Tool):
    name = "phone_camera_photo"
    description = (
        "Take a photo with the phone camera. Returns the saved file path. "
        "Requires Termux:API + camera permission. "
        "Saves to HELIX_HOME/camera/<timestamp>.jpg."
    )
    parameters = {
        "type": "object",
        "properties": {
            "camera": {"type": "integer", "default": 0, "description": "0=back, 1=front."},
            "save_path": {"type": "string", "default": "", "description": "Override save path."},
        },
    }
    tags = ["phone", "camera"]

    async def run(self, camera: int = 0, save_path: str = "") -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        import time
        if save_path:
            target = Path(save_path).expanduser()
        else:
            target = self.config.home / "camera" / f"photo_{int(time.time())}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        code, out = await run_cmd(
            f"termux-camera-photo -c {camera} {target}", timeout=30
        )
        if code != 0:
            return ToolResult.err(f"Photo failed: {out}")
        if not target.exists():
            return ToolResult.err(f"Photo command succeeded but file not found at {target}")
        return ToolResult.ok(
            f"Photo saved: {target} ({target.stat().st_size} bytes)",
            path=str(target), size=target.stat().st_size,
        )
