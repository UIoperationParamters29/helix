"""Hardware tools — battery, sensor, torch, vibrator, brightness, volume."""
from __future__ import annotations

import shlex
from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneBattery(Tool):
    name = "phone_battery"
    description = "Get battery status (percentage, temperature, charging state)."
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["phone", "hardware"]

    async def run(self) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd("termux-battery-status", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(out)


@tool
class PhoneSensor(Tool):
    name = "phone_sensor"
    description = "Read phone sensors (accelerometer, gyroscope, light, etc.). Returns JSON."
    parameters = {
        "type": "object",
        "properties": {
            "sensor": {"type": "string", "default": "", "description": "Specific sensor name. Empty = all."},
            "delay_ms": {"type": "integer", "default": 1000, "description": "Sampling delay in ms."},
        },
    }
    read_only = True
    tags = ["phone", "hardware", "sensor"]

    async def run(self, sensor: str = "", delay_ms: int = 1000) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        cmd = f"termux-sensor -n 1 -d {delay_ms}"
        if sensor:
            cmd += f" -s {shlex.quote(sensor)}"
        code, out = await run_cmd(cmd, timeout=15)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(out)


@tool
class PhoneTorch(Tool):
    name = "phone_torch"
    description = "Toggle the phone's flashlight (torch) on or off."
    parameters = {
        "type": "object",
        "properties": {"on": {"type": "boolean"}},
        "required": ["on"],
    }
    tags = ["phone", "hardware"]

    async def run(self, on: bool) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        cmd = "termux-torch on" if on else "termux-torch off"
        code, out = await run_cmd(cmd, timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Torch {'on' if on else 'off'}")


@tool
class PhoneVibrate(Tool):
    name = "phone_vibrate"
    description = "Vibrate the phone for N milliseconds."
    parameters = {
        "type": "object",
        "properties": {"duration_ms": {"type": "integer", "default": 500}},
    }
    tags = ["phone", "hardware"]

    async def run(self, duration_ms: int = 500) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(f"termux-vibrate -d {duration_ms} -f", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Vibrated {duration_ms}ms")


@tool
class PhoneVolume(Tool):
    name = "phone_volume"
    description = "Set media/music volume (0-15)."
    parameters = {
        "type": "object",
        "properties": {
            "volume": {"type": "integer", "description": "0-15"},
            "stream": {"type": "string", "enum": ["music", "ring", "notification", "alarm"], "default": "music"},
        },
        "required": ["volume"],
    }
    tags = ["phone", "hardware"]

    async def run(self, volume: int, stream: str = "music") -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(f"termux-volume {stream} {volume}", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Volume {stream} set to {volume}")


@tool
class PhoneBrightness(Tool):
    name = "phone_brightness"
    description = "Set screen brightness (0-255)."
    parameters = {
        "type": "object",
        "properties": {"brightness": {"type": "integer", "description": "0-255"}},
        "required": ["brightness"],
    }
    tags = ["phone", "hardware"]

    async def run(self, brightness: int) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(f"termux-brightness {max(0, min(255, brightness))}", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Brightness set to {brightness}")
