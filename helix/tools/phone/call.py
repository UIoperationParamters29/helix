"""Phone call tool — initiate calls via Termux:API."""
from __future__ import annotations

from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneCall(Tool):
    name = "phone_call"
    description = "Initiate a phone call. DANGEROUS. Requires Termux:API."
    parameters = {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
        },
        "required": ["phone"],
    }
    dangerous = True
    tags = ["phone", "call"]

    async def run(self, phone: str) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(f"termux-telephony-call {phone}")
        if code != 0:
            return ToolResult.err(f"Call failed: {out}", phone=phone)
        return ToolResult.ok(f"Calling {phone}...", phone=phone)
