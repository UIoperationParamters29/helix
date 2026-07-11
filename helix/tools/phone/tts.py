"""TTS tool — text-to-speech via Termux:API."""
from __future__ import annotations

import shlex
from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneTTS(Tool):
    name = "phone_tts"
    description = "Speak text aloud using Android text-to-speech."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "language": {"type": "string", "default": "en", "description": "ISO 639-1 (e.g. en, ar, zh, es)."},
            "pitch": {"type": "integer", "default": 100, "description": "1-200 (100=normal)."},
            "rate": {"type": "integer", "default": 100, "description": "1-200 (100=normal)."},
        },
        "required": ["text"],
    }
    tags = ["phone", "audio"]

    async def run(self, text: str, language: str = "en",
                  pitch: int = 100, rate: int = 100) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        cmd = (f"termux-tts-speak -l {shlex.quote(language)} "
               f"-p {pitch} -r {rate}")
        # Pass text via stdin
        import asyncio
        proc = await asyncio.create_subprocess_shell(
            cmd, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate(text.encode("utf-8"))
        if proc.returncode == 0:
            return ToolResult.ok(f"Spoke: {text[:80]}{'...' if len(text)>80 else ''}")
        return ToolResult.err(f"TTS failed: {out.decode('utf-8', errors='replace') if out else ''}")
