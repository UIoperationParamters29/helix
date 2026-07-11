"""SMS tools — send + read SMS via Termux:API."""
from __future__ import annotations

from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneSmsSend(Tool):
    name = "phone_sms_send"
    description = "Send an SMS message. Requires Termux:API. DANGEROUS: costs money / can spam contacts."
    parameters = {
        "type": "object",
        "properties": {
            "phone": {"type": "string", "description": "Phone number (E.164 preferred, e.g. +14155551234)."},
            "message": {"type": "string", "description": "Message text."},
        },
        "required": ["phone", "message"],
    }
    dangerous = True
    tags = ["phone", "sms"]

    async def run(self, phone: str, message: str) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        # termux-sms-send -n <number> <message  (message via stdin to avoid quoting issues)
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "termux-sms-send", "-n", phone,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate(message.encode("utf-8"))
        out_s = out.decode("utf-8", errors="replace") if out else ""
        if proc.returncode == 0:
            return ToolResult.ok(f"SMS sent to {phone}: {message[:80]}", phone=phone)
        return ToolResult.err(f"SMS failed: {out_s}", phone=phone)


@tool
class PhoneSmsRead(Tool):
    name = "phone_sms_read"
    description = "Read recent SMS messages. Requires Termux:API. Returns JSON list."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 10},
            "offset": {"type": "integer", "default": 0},
        },
    }
    read_only = True
    tags = ["phone", "sms"]

    async def run(self, limit: int = 10, offset: int = 0) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(
            f"termux-sms-list -l {limit} -o {offset}", timeout=20
        )
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(out, count=limit, offset=offset)
