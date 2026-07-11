"""Memory tools — agent-editable persistent memory.

The agent owns MEMORY.md and USER.md in HELIX_HOME. It edits these
between turns to capture facts about the user, prior tasks, and itself.
On next session, the system prompt pulls these in.

This is the closed learning loop (stolen from Hermes).
"""
from __future__ import annotations

from pathlib import Path

from .base import Tool, ToolResult, tool


def _memory_file(home: Path, kind: str) -> Path:
    return home / f"{kind}.md"


def load_memory(home: Path) -> dict[str, str]:
    """Load MEMORY.md and USER.md content for system prompt."""
    out = {}
    for kind in ("IDENTITY", "USER", "MEMORY"):
        f = _memory_file(home, kind)
        if f.exists():
            out[kind] = f.read_text(encoding="utf-8")
    return out


@tool
class MemoryRead(Tool):
    name = "memory_read"
    description = "Read a memory file: 'IDENTITY' (agent persona), 'USER' (user facts), or 'MEMORY' (general notes)."
    parameters = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["IDENTITY", "USER", "MEMORY"]},
        },
        "required": ["kind"],
    }
    read_only = True
    tags = ["memory"]

    async def run(self, kind: str) -> ToolResult:
        f = _memory_file(self.config.home, kind)
        if not f.exists():
            return ToolResult.ok(f"({kind} is empty — initialize it with memory_update)",
                                 kind=kind, exists=False)
        return ToolResult.ok(f.read_text(encoding="utf-8"), kind=kind, path=str(f))


@tool
class MemoryUpdate(Tool):
    name = "memory_update"
    description = (
        "Update a memory file. Use to persist facts about the user, "
        "lessons learned, or refine the agent persona. "
        "Modes: 'append' (add to end), 'replace' (full overwrite), "
        "'edit' (find/replace unique old_str). "
        "MEMORY is for general facts. USER is for user preferences. "
        "IDENTITY is the agent's persona (rarely changed). "
        "After solving a non-trivial task, CONSIDER appending a lesson to MEMORY."
    )
    parameters = {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["IDENTITY", "USER", "MEMORY"]},
            "mode": {"type": "string", "enum": ["append", "replace", "edit"], "default": "append"},
            "content": {"type": "string", "description": "Content to write (append/replace) OR new text (edit)."},
            "old_str": {"type": "string", "description": "For edit mode: exact text to find."},
        },
        "required": ["kind", "mode", "content"],
    }
    tags = ["memory", "self-improvement"]

    async def run(self, kind: str, mode: str, content: str, old_str: str = "") -> ToolResult:
        f = _memory_file(self.config.home, kind)
        f.parent.mkdir(parents=True, exist_ok=True)

        if mode == "replace":
            f.write_text(content, encoding="utf-8")
            return ToolResult.ok(f"Replaced {kind} ({len(content)} chars)", kind=kind, path=str(f))
        elif mode == "append":
            existing = f.read_text(encoding="utf-8") if f.exists() else ""
            new = existing + ("\n\n" if existing and not existing.endswith("\n") else "") + content
            f.write_text(new, encoding="utf-8")
            return ToolResult.ok(f"Appended {len(content)} chars to {kind}", kind=kind, path=str(f))
        elif mode == "edit":
            if not old_str:
                return ToolResult.err("old_str required for edit mode")
            if not f.exists():
                return ToolResult.err(f"{kind} does not exist yet — use replace first")
            text = f.read_text(encoding="utf-8")
            count = text.count(old_str)
            if count == 0:
                return ToolResult.err("old_str not found")
            if count > 1:
                return ToolResult.err(f"old_str matches {count} times — must be unique")
            new = text.replace(old_str, content, 1)
            f.write_text(new, encoding="utf-8")
            return ToolResult.ok(f"Edited {kind}", kind=kind, path=str(f))
        return ToolResult.err(f"Unknown mode: {mode}")
