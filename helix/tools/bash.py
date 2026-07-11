"""bash tool — run shell commands.

The single most powerful tool. Code is the universal action (OpenHands principle).
On phone: runs in Termux shell with full filesystem access.
On PC: runs locally (optionally sandboxed via DockerWorkspace).
"""
from __future__ import annotations

import asyncio, re
from typing import Any

from .base import Tool, ToolResult, tool
from ..config import HelixConfig


@tool
class Bash(Tool):
    name = "bash"
    description = (
        "Execute a shell command on the host (Termux on Android, local shell on PC). "
        "Returns combined stdout+stderr, exit code, and runtime. "
        "Use this for: file operations, package management, git, system queries, "
        "running scripts, controlling other CLI tools. "
        "Avoid: extremely long-running commands (use timeout). "
        "DANGEROUS patterns will be blocked unless auto_approve_writes=True."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 30).", "default": 30},
            "cwd": {"type": "string", "description": "Working directory (default: HELIX_HOME).", "default": ""},
        },
        "required": ["command"],
    }
    tags = ["shell", "system"]
    read_only = False

    def check_dangerous(self, args: dict) -> bool:
        cmd = args.get("command", "")
        for pat in self.config.dangerous_patterns:
            if re.search(pat, cmd):
                return True
        return False

    async def run(self, command: str, timeout: int = 30, cwd: str = "") -> ToolResult:
        work_dir = cwd or str(self.config.home)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=work_dir,
                env={**__import__("os").environ, "TERM": "dumb"},
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult.err(
                    f"Command timed out after {timeout}s: {command}",
                    exit_code=-1, timed_out=True,
                )
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            if len(output) > 50_000:
                output = output[:25_000] + f"\n\n[...truncated {len(output)-50_000} chars...]\n\n" + output[-25_000:]
            return ToolResult.ok(
                output if output else "(no output)",
                exit_code=proc.returncode,
                command=command,
            )
        except Exception as e:
            return ToolResult.err(f"Failed to execute: {e}", command=command)
