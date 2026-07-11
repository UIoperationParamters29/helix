"""Notification tool — post + read Android notifications via Termux:API."""
from __future__ import annotations

from ..base import Tool, ToolResult, tool
from ._common import is_termux, termux_api_available, run_cmd, not_termux_error, no_api_error


@tool
class PhoneNotify(Tool):
    name = "phone_notification"
    description = "Post a system notification on the phone."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string", "default": ""},
            "id": {"type": "integer", "default": 1, "description": "Notification ID (use same ID to update)."},
        },
        "required": ["title"],
    }
    tags = ["phone", "notification"]

    async def run(self, title: str, body: str = "", id: int = 1) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        import shlex
        cmd = f"termux-notification --id {id} --title {shlex.quote(title)} --content {shlex.quote(body)}"
        code, out = await run_cmd(cmd)
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Notification posted (id={id})", title=title)


@tool
class PhoneNotifyRead(Tool):
    name = "phone_notification_list"
    description = "List active notifications. Requires Notification Listener permission."
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["phone", "notification"]

    async def run(self) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd("termux-notification-list", timeout=10)
        if code != 0:
            return ToolResult.err(f"Failed: {out}\nNote: requires Notification access permission in Android settings.")
        return ToolResult.ok(out)


@tool
class PhoneNotifyRemove(Tool):
    name = "phone_notification_remove"
    description = "Cancel a previously posted notification by ID."
    parameters = {
        "type": "object",
        "properties": {"id": {"type": "integer"}},
        "required": ["id"],
    }
    tags = ["phone", "notification"]

    async def run(self, id: int) -> ToolResult:
        if not is_termux():
            return not_termux_error(self.name)
        if not termux_api_available():
            return no_api_error(self.name)
        code, out = await run_cmd(f"termux-notification-remove {id}")
        if code != 0:
            return ToolResult.err(f"Failed: {out}")
        return ToolResult.ok(f"Removed notification id={id}")
