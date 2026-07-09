"""Shared helpers for phone tools."""
from __future__ import annotations

import asyncio, shutil, os
from pathlib import Path
from typing import Any

from ..base import ToolResult


def is_termux() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "") or Path("/data/data/com.termux").exists()


def termux_api_available() -> bool:
    """Is the `termux-api` CLI installed?"""
    return shutil.which("termux-api") is not None or shutil.which("termux-sms-send") is not None


def adb_available() -> bool:
    return shutil.which("adb") is not None


async def run_cmd(cmd: str, timeout: int = 15) -> tuple[int, str]:
    """Run a shell command, return (exit_code, combined_output)."""
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "TERM": "dumb"},
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, out.decode("utf-8", errors="replace") if out else ""
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, f"(timed out after {timeout}s)"


def not_termux_error(tool_name: str) -> ToolResult:
    return ToolResult.err(
        f"{tool_name} requires Termux. Install Termux from F-Droid, then run: "
        f"pkg install termux-api && pip install helix-agent. "
        f"See docs/PHONE_SETUP.md."
    )


def no_api_error(tool_name: str) -> ToolResult:
    return ToolResult.err(
        f"{tool_name} requires the Termux:API package. Run: pkg install termux-api. "
        f"Also install the Termux:API app from F-Droid."
    )


def no_adb_error(tool_name: str) -> ToolResult:
    return ToolResult.err(
        f"{tool_name} requires ADB. In Termux run: pkg install android-tools. "
        f"Then pair your phone to itself (see docs/PHONE_SETUP.md). "
        f"On PC, install platform-tools and connect via USB/WiFi."
    )


async def adb_shell(cmd: str, timeout: int = 15) -> tuple[int, str]:
    """Run `adb shell <cmd>`. Uses configured adb_address if set."""
    # The caller should pass a shell-quoted command
    full = "adb shell " + cmd
    return await run_cmd(full, timeout=timeout)
