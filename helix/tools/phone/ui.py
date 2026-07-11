"""UI automation tools — tap/swipe/type/screenshot via ADB.

These work via self-ADB (phone controlling itself via wireless ADB) or
via Shizuku (no ADB dance). On PC, can control any connected device.

Setup:
  1. In Termux: pkg install android-tools
  2. On phone: enable Wireless debugging in Developer Options
  3. Pair: adb pair <ip:port> (enter pairing code)
  4. Connect: adb connect <ip:port>

See docs/PHONE_SETUP.md for full instructions.
"""
from __future__ import annotations

import asyncio, base64, time, shlex
from pathlib import Path

from ..base import Tool, ToolResult, tool
from ._common import is_termux, adb_available, run_cmd, not_termux_error, no_adb_error


async def _adb(cmd: str, timeout: int = 15) -> tuple[int, str]:
    """Run `adb shell <cmd>`."""
    full = f"adb shell {cmd}"
    return await run_cmd(full, timeout=timeout)


@tool
class PhoneUiTap(Tool):
    name = "phone_ui_tap"
    description = "Tap the screen at (x, y) pixel coordinates via ADB."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    }
    tags = ["phone", "ui"]

    async def run(self, x: int, y: int) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb(f"input tap {x} {y}")
        if code != 0:
            return ToolResult.err(f"Tap failed: {out}")
        return ToolResult.ok(f"Tapped ({x}, {y})")


@tool
class PhoneUiSwipe(Tool):
    name = "phone_ui_swipe"
    description = "Swipe from (x1,y1) to (x2,y2) over duration_ms."
    parameters = {
        "type": "object",
        "properties": {
            "x1": {"type": "integer"}, "y1": {"type": "integer"},
            "x2": {"type": "integer"}, "y2": {"type": "integer"},
            "duration_ms": {"type": "integer", "default": 300},
        },
        "required": ["x1", "y1", "x2", "y2"],
    }
    tags = ["phone", "ui"]

    async def run(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        if code != 0:
            return ToolResult.err(f"Swipe failed: {out}")
        return ToolResult.ok(f"Swiped ({x1},{y1}) -> ({x2},{y2}) in {duration_ms}ms")


@tool
class PhoneUiType(Tool):
    name = "phone_ui_type"
    description = "Type text into the currently focused field. Spaces become %s in ADB."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    tags = ["phone", "ui"]

    async def run(self, text: str) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        # ADB input text requires escaping: spaces -> %s
        # Use shlex.quote to be safe; for many special chars we fall back to keyboard keyevent
        safe = text.replace(" ", "%s")
        # Limit per-call length (ADB has ~4k limit on input text)
        if len(safe) > 1000:
            return ToolResult.err("Text too long for single ADB input call (>1000 chars). Split into chunks.")
        code, out = await _adb(f"input text {shlex.quote(safe)}")
        if code != 0:
            return ToolResult.err(f"Type failed: {out}")
        return ToolResult.ok(f"Typed: {text[:80]}{'...' if len(text)>80 else ''}")


@tool
class PhoneUiKey(Tool):
    name = "phone_ui_key"
    description = (
        "Press a hardware key. Common keycodes: "
        "4=BACK, 3=HOME, 24=VOL_UP, 25=VOL_DOWN, 26=POWER, "
        "66=ENTER, 67=DEL, 84=SEARCH, 187=APP_SWITCH."
    )
    parameters = {
        "type": "object",
        "properties": {"keycode": {"type": "integer"}},
        "required": ["keycode"],
    }
    tags = ["phone", "ui"]

    async def run(self, keycode: int) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb(f"input keyevent {keycode}")
        if code != 0:
            return ToolResult.err(f"Key failed: {out}")
        return ToolResult.ok(f"Pressed keycode {keycode}")


@tool
class PhoneUiScreenshot(Tool):
    name = "phone_ui_screenshot"
    description = (
        "Take a screenshot of the phone screen. Saves PNG to HELIX_HOME/screenshots/. "
        "Returns the local file path. The agent can then read it via file_read (with VLM)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "save_path": {"type": "string", "default": ""},
        },
    }
    read_only = True
    tags = ["phone", "ui", "camera"]

    async def run(self, save_path: str = "") -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        if save_path:
            target = Path(save_path).expanduser()
        else:
            target = self.config.home / "screenshots" / f"shot_{int(time.time())}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Save to device first, then pull
        device_path = f"/sdcard/helix_shot_{int(time.time())}.png"
        code, out = await _adb(f"screencap -p {device_path}", timeout=15)
        if code != 0:
            return ToolResult.err(f"Screenshot failed: {out}")
        # Pull to local
        code, out = await run_cmd(f"adb pull {device_path} {target}", timeout=20)
        if code != 0:
            return ToolResult.err(f"Pull failed: {out}")
        # Cleanup device
        await _adb(f"rm {device_path}")
        size = target.stat().st_size if target.exists() else 0
        return ToolResult.ok(
            f"Screenshot saved: {target} ({size} bytes)",
            path=str(target), size=size,
        )


@tool
class PhoneUiDump(Tool):
    name = "phone_ui_dump"
    description = (
        "Dump the current screen's UI hierarchy as XML. "
        "Reveals all visible elements with their bounds, text, content-desc. "
        "Use this to find what to tap. Saved to HELIX_HOME/ui_dumps/."
    )
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["phone", "ui"]

    async def run(self) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        device_path = f"/sdcard/helix_ui_{int(time.time())}.xml"
        code, out = await _adb(f"uiautomator dump {device_path}", timeout=15)
        if code != 0:
            return ToolResult.err(f"UI dump failed: {out}")
        # Pull and read
        target = self.config.home / "ui_dumps" / f"ui_{int(time.time())}.xml"
        target.parent.mkdir(parents=True, exist_ok=True)
        code, out = await run_cmd(f"adb pull {device_path} {target}", timeout=15)
        if code != 0:
            return ToolResult.err(f"Pull failed: {out}")
        await _adb(f"rm {device_path}")
        try:
            xml = target.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult.err(f"Read failed: {e}")
        # Truncate if huge
        if len(xml) > 30000:
            xml = xml[:15000] + "\n[...truncated...]\n" + xml[-15000:]
        return ToolResult.ok(xml, path=str(target))


@tool
class PhoneScreenState(Tool):
    name = "phone_screen_state"
    description = "Check if screen is on/off and get display info."
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["phone", "ui"]

    async def run(self) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb("dumpsys power | grep 'mWakefulness='", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(out.strip(), raw=out)


@tool
class PhoneScreenWake(Tool):
    name = "phone_screen_wake"
    description = "Wake the screen (turn display on) or put it to sleep."
    parameters = {
        "type": "object",
        "properties": {"on": {"type": "boolean"}},
        "required": ["on"],
    }
    tags = ["phone", "ui"]

    async def run(self, on: bool) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        if on:
            # Wake + dismiss lock
            await _adb("input keyevent 26")  # POWER
            await asyncio.sleep(0.3)
            await _adb("input keyevent 82")  # MENU (unlock)
            return ToolResult.ok("Screen woken")
        else:
            await _adb("input keyevent 26")
            return ToolResult.ok("Screen put to sleep")
