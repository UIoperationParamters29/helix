"""Termux workspace — same as local but with Termux-specific detection + helpers."""
from __future__ import annotations
import shutil
from pathlib import Path

from .local import LocalWorkspace


class TermuxWorkspace(LocalWorkspace):
    """Runs commands inside Termux. Same as local but knows about termux-api + adb."""

    @property
    def kind(self) -> str:
        return "termux"

    def termux_api_ready(self) -> bool:
        return shutil.which("termux-sms-send") is not None

    def adb_ready(self) -> bool:
        return shutil.which("adb") is not None

    async def ensure_deps(self) -> str:
        """Install termux-api + android-tools if missing. Returns install log."""
        log = []
        if not self.termux_api_ready():
            code, out = await self.execute("pkg install -y termux-api", timeout=120)
            log.append(f"termux-api: {out}")
        if not self.adb_ready():
            code, out = await self.execute("pkg install -y android-tools", timeout=120)
            log.append(f"android-tools: {out}")
        return "\n".join(log)
