"""Clipboard tools — get/set Android clipboard via Termux:API."""
from __future__ import annotations

import shlex
from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneClipboardGet(Tool):
    name = "phone_clipboard_get"
    description = "Get current Android clipboard content."
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["phone", "clipboard"]

    async def run(self) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd("termux-clipboard-get")
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(out)


@tool
class PhoneClipboardSet(Tool):
    name = "phone_clipboard_set"
    description = "Set the Android clipboard."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    tags = ["phone", "clipboard"]

    async def run(self, text: str) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        # Use stdin to avoid quoting issues
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "termux-clipboard-set",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate(text.encode("utf-8"))
        if proc.returncode == 0:
            return ToolResult.ok(f"Clipboard set ({len(text)} chars)")
        return ToolResult.err(f"Failed: {out.decode('utf-8', errors='replace') if out else ''}")
