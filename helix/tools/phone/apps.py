"""App management tools — launch apps, list installed apps, get current foreground app."""
from __future__ import annotations

import shlex
from ..base import Tool, ToolResult, tool
from ._common import adb_available, run_cmd, no_adb_error


async def _adb(cmd: str, timeout: int = 15) -> tuple[int, str]:
    full = f"adb shell {cmd}"
    return await run_cmd(full, timeout=timeout)


@tool
class PhoneAppLaunch(Tool):
    name = "phone_app_launch"
    description = (
        "Launch an app by package name or URL. "
        "Examples: 'com.android.chrome' to open Chrome, "
        "or a URL like 'https://example.com' to open in default browser, "
        "or 'youtube' to search and launch. "
        "For specific deep links, pass the full URL."
    )
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Package name, URL, or app name."},
            "action": {"type": "string", "default": "android.intent.action.VIEW",
                        "description": "Android intent action. Default opens URLs."},
        },
        "required": ["target"],
    }
    tags = ["phone", "apps"]

    async def run(self, target: str, action: str = "android.intent.action.VIEW") -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        if target.startswith(("http://", "https://")):
            cmd = f"am start -a {action} -d {shlex.quote(target)}"
        elif "." in target and " " not in target:
            # Looks like a package name
            cmd = f"monkey -p {shlex.quote(target)} -c android.intent.category.LAUNCHER 1"
        else:
            # Try to find package by name
            cmd = f"monkey -p {shlex.quote(target)} -c android.intent.category.LAUNCHER 1"
        code, out = await _adb(cmd, timeout=15)
        if code != 0:
            return ToolResult.err(f"Launch failed: {out}")
        return ToolResult.ok(f"Launched: {target}", target=target, output=out)


@tool
class PhoneAppList(Tool):
    name = "phone_app_list"
    description = "List all installed apps (package names)."
    parameters = {
        "type": "object",
        "properties": {
            "filter": {"type": "string", "default": "", "description": "Substring filter (e.g. 'chrome', 'whatsapp')."},
        },
    }
    read_only = True
    tags = ["phone", "apps"]

    async def run(self, filter: str = "") -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb("pm list packages", timeout=20)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        lines = [l.replace("package:", "").strip() for l in out.splitlines() if l.startswith("package:")]
        if filter:
            lines = [l for l in lines if filter.lower() in l.lower()]
        lines.sort()
        out_text = "\n".join(lines[:500])
        if len(lines) > 500:
            out_text += f"\n\n[...{len(lines)-500} more...]"
        return ToolResult.ok(out_text, count=len(lines))


@tool
class PhoneAppCurrent(Tool):
    name = "phone_app_current"
    description = "Get the currently focused app and activity."
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["phone", "apps"]

    async def run(self) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb("dumpsys activity activities | grep mResumedActivity", timeout=10)
        if code != 0:
            # Fallback
            code, out = await _adb("dumpsys window | grep mCurrentFocus", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(out.strip())


@tool
class PhoneAppStop(Tool):
    name = "phone_app_stop"
    description = "Force-stop an app by package name."
    parameters = {
        "type": "object",
        "properties": {"package": {"type": "string"}},
        "required": ["package"],
    }
    tags = ["phone", "apps"]

    async def run(self, package: str) -> ToolResult:
        if not adb_available():
            return no_adb_error(self.name)
        code, out = await _adb(f"am force-stop {shlex.quote(package)}", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Stopped: {package}")
