"""Location tool — get GPS coordinates via Termux:API."""
from __future__ import annotations

from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneLocation(Tool):
    name = "phone_location"
    description = "Get current GPS location. Requires Termux:API + location permission."
    parameters = {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "enum": ["gps", "network", "passive"], "default": "network"},
        },
    }
    read_only = True
    tags = ["phone", "location"]

    async def run(self, provider: str = "network") -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(f"termux-location -p {provider}", timeout=30)
        if code != 0:
            return ToolResult.err(f"Location failed: {out}")
        return ToolResult.ok(out, provider=provider)
