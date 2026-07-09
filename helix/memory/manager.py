"""Memory manager — load IDENTITY/USER/MEMORY for system prompt."""
from __future__ import annotations
from pathlib import Path


def load_memory(home: Path) -> dict[str, str]:
    """Load all memory files."""
    out = {}
    for kind in ("IDENTITY", "USER", "MEMORY"):
        f = home / f"{kind}.md"
        if f.exists():
            out[kind] = f.read_text(encoding="utf-8")
    return out


def load_memory_for_prompt(home: Path) -> dict[str, str]:
    return load_memory(home)


def init_memory_files(home: Path, persona: str = "HELIX") -> None:
    """Create default memory files if missing."""
    defaults = {
        "IDENTITY": f"# {persona}\n\nYou are {persona}, a self-improving agent.\nYou help the user accomplish tasks on their phone and PC.\nYou learn from each interaction and write skills for future reuse.\n",
        "USER": "# User\n\n(Add facts about the user as you learn them: name, preferences, ongoing projects.)\n",
        "MEMORY": "# Memory\n\n(Persistent notes. Add lessons learned, recurring patterns, important context.)\n",
    }
    for kind, content in defaults.items():
        f = home / f"{kind}.md"
        if not f.exists():
            f.write_text(content, encoding="utf-8")
