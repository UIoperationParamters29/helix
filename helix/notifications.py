"""HELIX notifications — ongoing task indicator + wake lock for Termux.

Shows an ongoing Android notification while HELIX is working on a task,
so the user knows it's active even when Termux is in the background.
Auto-removes the notification when the task completes.
"""
from __future__ import annotations

import asyncio, shutil, subprocess
from pathlib import Path


def _is_termux() -> bool:
    import os
    return "com.termux" in os.environ.get("PREFIX", "") or Path("/data/data/com.termux").exists()


def _termux_api_available() -> bool:
    return shutil.which("termux-notification") is not None


_NOTIF_ID = 7777  # fixed ID so we can update/remove the same notification


async def start_task_notification(task_description: str = "Working on task...") -> None:
    """Show an ongoing notification + acquire wake lock.

    Call this when HELIX starts processing a user request.
    Only works on Termux with termux-api installed. No-op elsewhere.
    """
    if not _is_termux() or not _termux_api_available():
        return
    try:
        # Acquire wake lock so Termux doesn't get killed in background
        subprocess.Popen(["termux-wake-lock"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Show ongoing notification (can't be swiped away)
        subprocess.Popen([
            "termux-notification",
            "--id", str(_NOTIF_ID),
            "--title", "HELIX working",
            "--content", task_description[:200],
            "--ongoing",       # can't be dismissed
            "--priority", "high",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


async def update_task_notification(progress: str) -> None:
    """Update the ongoing notification with progress text."""
    if not _is_termux() or not _termux_api_available():
        return
    try:
        subprocess.Popen([
            "termux-notification",
            "--id", str(_NOTIF_ID),
            "--title", "HELIX working",
            "--content", progress[:200],
            "--ongoing",
            "--priority", "high",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


async def end_task_notification(summary: str = "Task complete") -> None:
    """Remove the ongoing notification + release wake lock.

    Shows a brief (non-ongoing) notification that the task is done,
    then releases the wake lock.
    """
    if not _is_termux() or not _termux_api_available():
        return
    try:
        # Cancel the ongoing notification
        subprocess.Popen(["termux-notification-remove", str(_NOTIF_ID)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Show a brief completion notification (auto-dismissable)
        subprocess.Popen([
            "termux-notification",
            "--title", "HELIX done",
            "--content", summary[:200],
            "--priority", "default",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Release wake lock
        subprocess.Popen(["termux-wake-unlock"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
