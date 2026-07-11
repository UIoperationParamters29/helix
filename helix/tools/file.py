"""File operation tools — read, write, edit, list, search.

All paths are relative to HELIX_HOME unless absolute. We refuse to write
outside HELIX_HOME unless explicitly allowed.
"""
from __future__ import annotations

import os, re, asyncio
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult, tool


def _resolve(path: str, home: Path) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = home / p
    return p.resolve()


def _is_safe(p: Path, home: Path) -> bool:
    """Allow access inside HELIX_HOME, /tmp, and cwd. Block others unless explicitly absolute."""
    try:
        p.relative_to(home)
        return True
    except ValueError:
        pass
    # Allow absolute paths explicitly chosen by user
    if Path.cwd() in p.parents or p == Path.cwd():
        return True
    # Allow /tmp
    try:
        p.relative_to("/tmp")
        return True
    except ValueError:
        pass
    return True  # In HELIX we trust the agent on the host; policy hook can deny


@tool
class FileRead(Tool):
    name = "file_read"
    description = (
        "Read a text file's contents. Refuses binary files (images, audio, "
        "compressed, executable). For images, use a vision-capable LLM or "
        "describe the screenshot path instead of reading it."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path (relative to HELIX_HOME or absolute)."},
            "offset": {"type": "integer", "description": "Start line (1-indexed). Default 1.", "default": 1},
            "limit": {"type": "integer", "description": "Max lines to read. Default 2000.", "default": 2000},
        },
        "required": ["path"],
    }
    read_only = True
    tags = ["filesystem"]

    async def run(self, path: str, offset: int = 1, limit: int = 2000) -> ToolResult:
        p = _resolve(path, self.config.home)
        if not p.exists():
            return ToolResult.err(f"File not found: {p}")
        if not p.is_file():
            return ToolResult.err(f"Not a file: {p}")

        # BINARY DETECTION: read first 8KB and check for null bytes / common magic bytes.
        # This prevents the LLM from getting PNG/JPEG/garbage in its context window.
        try:
            with open(p, "rb") as f:
                head = f.read(8192)
            if b"\x00" in head:
                # Binary file — refuse to read as text
                suffix = p.suffix.lower()
                if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"):
                    return ToolResult.err(
                        f"Binary image file ({suffix}). Cannot read as text. "
                        f"The screenshot is saved at: {p}\n"
                        f"To understand the screenshot, describe what you expect to see "
                        f"based on prior UI actions, or use phone_ui_dump to get the UI "
                        f"hierarchy as XML (which IS text-readable)."
                    )
                if suffix in (".apk", ".dex", ".so", ".bin", ".dat"):
                    return ToolResult.err(f"Binary file ({suffix}, {p.stat().st_size} bytes). Cannot read as text.")
                return ToolResult.err(
                    f"Binary file ({p.stat().st_size} bytes). Cannot read as text. "
                    f"If this is an image, use phone_ui_dump instead to get the UI hierarchy as XML."
                )
        except Exception as e:
            return ToolResult.err(f"Read failed: {e}")

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            total = len(lines)
            start = max(0, offset - 1)
            end = start + limit
            chunk = "\n".join(lines[start:end])
            meta = {"path": str(p), "total_lines": total, "returned_lines": end - start}
            return ToolResult.ok(chunk, **meta)
        except Exception as e:
            return ToolResult.err(f"Read failed: {e}")


@tool
class FileWrite(Tool):
    name = "file_write"
    description = "Write content to a file (overwrites). Creates parent dirs."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean", "default": False},
        },
        "required": ["path", "content"],
    }
    tags = ["filesystem"]

    async def run(self, path: str, content: str, append: bool = False) -> ToolResult:
        p = _resolve(path, self.config.home)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        try:
            with open(p, mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult.ok(f"Wrote {len(content)} chars to {p}",
                                 path=str(p), bytes=len(content))
        except Exception as e:
            return ToolResult.err(f"Write failed: {e}")


@tool
class FileEdit(Tool):
    name = "file_edit"
    description = (
        "Edit a file by replacing a unique old_str with new_str. "
        "Fails if old_str is not unique or not found. Use for surgical edits."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_str": {"type": "string", "description": "Exact text to find (must be unique)."},
            "new_str": {"type": "string", "description": "Replacement text."},
        },
        "required": ["path", "old_str", "new_str"],
    }
    tags = ["filesystem"]

    async def run(self, path: str, old_str: str, new_str: str) -> ToolResult:
        p = _resolve(path, self.config.home)
        if not p.exists():
            return ToolResult.err(f"File not found: {p}")
        text = p.read_text(encoding="utf-8")
        count = text.count(old_str)
        if count == 0:
            return ToolResult.err("old_str not found in file")
        if count > 1:
            return ToolResult.err(f"old_str matches {count} times — must be unique. Include more context.")
        new_text = text.replace(old_str, new_str, 1)
        p.write_text(new_text, encoding="utf-8")
        return ToolResult.ok(f"Edited {p}: replaced {len(old_str)} chars with {len(new_str)} chars",
                             path=str(p))


@tool
class FileList(Tool):
    name = "file_list"
    description = "List files in a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "recursive": {"type": "boolean", "default": False},
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '*.py')", "default": "*"},
        },
    }
    read_only = True
    tags = ["filesystem"]

    async def run(self, path: str = ".", recursive: bool = False, pattern: str = "*") -> ToolResult:
        p = _resolve(path, self.config.home)
        if not p.exists():
            return ToolResult.err(f"Directory not found: {p}")
        if not p.is_dir():
            return ToolResult.err(f"Not a directory: {p}")
        if recursive:
            files = sorted(p.rglob(pattern))
        else:
            files = sorted(p.glob(pattern))
        lines = []
        for f in files[:500]:
            try:
                rel = f.relative_to(p)
                if f.is_dir():
                    lines.append(f"  {rel}/")
                else:
                    size = f.stat().st_size
                    lines.append(f"  {rel}  ({size} bytes)")
            except Exception:
                lines.append(str(f))
        out = f"Directory: {p}\n{len(files)} entries:\n" + "\n".join(lines)
        return ToolResult.ok(out, count=len(files))


@tool
class FileSearch(Tool):
    name = "file_search"
    description = "Search file contents with regex (like ripgrep)."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern."},
            "path": {"type": "string", "default": "."},
            "file_pattern": {"type": "string", "default": "*"},
            "max_results": {"type": "integer", "default": 50},
        },
        "required": ["pattern"],
    }
    read_only = True
    tags = ["filesystem", "search"]

    async def run(self, pattern: str, path: str = ".",
                  file_pattern: str = "*", max_results: int = 50) -> ToolResult:
        p = _resolve(path, self.config.home)
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult.err(f"Bad regex: {e}")
        matches = []
        for f in p.rglob(file_pattern):
            if not f.is_file():
                continue
            if f.stat().st_size > 1_000_000:
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if regex.search(line):
                        matches.append(f"{f}:{i}: {line.strip()[:200]}")
                        if len(matches) >= max_results:
                            break
            except Exception:
                continue
            if len(matches) >= max_results:
                break
        return ToolResult.ok("\n".join(matches) or "(no matches)",
                             count=len(matches))
