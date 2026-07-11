"""Local workspace — direct subprocess execution on the host."""
from __future__ import annotations
import asyncio, os
from pathlib import Path

from .base import Workspace


class LocalWorkspace(Workspace):
    """Runs commands directly on the host. No isolation."""

    @property
    def kind(self) -> str:
        return "local"

    async def execute(self, command: str, timeout: int = 30, cwd: str | None = None) -> tuple[int, str]:
        work_dir = cwd or str(self.config.home)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=work_dir,
            env={**os.environ, "TERM": "dumb"},
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode or 0, out.decode("utf-8", errors="replace") if out else ""
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, f"(timed out after {timeout}s)"
