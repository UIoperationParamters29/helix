"""Skills system — progressive disclosure + agent-authored learning.

A skill is a markdown document the agent writes itself after solving a
non-trivial task. Future sessions discover skills via Level-0 summaries
in the system prompt, and pull full content (Level 1) only when needed.

Three levels:
  Level 0: title + 1-line description (always in system prompt)
  Level 1: full SKILL.md content (pulled on demand via skill_read tool)
  Level 2: referenced files (pulled when skill instructs)

Skill location: HELIX_HOME/skills/<name>/SKILL.md
"""
from __future__ import annotations

import os, re
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult, tool


def _skills_dir(home: Path) -> Path:
    d = home / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_skill_summaries(home: Path) -> list[dict]:
    """Level-0: title + 1-line desc for every skill. Loaded into system prompt."""
    skills = []
    sd = _skills_dir(home)
    for d in sorted(sd.iterdir()):
        if not d.is_dir():
            continue
        sf = d / "SKILL.md"
        if not sf.exists():
            continue
        try:
            text = sf.read_text(encoding="utf-8")
            title = d.name
            # Try to extract H1
            m = re.match(r"^#\s+(.+)$", text, re.M)
            if m:
                title = m.group(1).strip()
            # First non-empty, non-heading line
            desc = ""
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    desc = line[:200]
                    break
            skills.append({
                "name": d.name,
                "title": title,
                "description": desc,
                "path": str(sf),
            })
        except Exception:
            continue
    return skills


@tool
class SkillList(Tool):
    name = "skill_list"
    description = "List all available skills (Level 0: names + 1-line descriptions)."
    parameters = {"type": "object", "properties": {}}
    read_only = True
    tags = ["skills"]

    async def run(self) -> ToolResult:
        skills = load_skill_summaries(self.config.home)
        if not skills:
            return ToolResult.ok("(no skills yet — agent can create them via skill_manage)")
        lines = [f"{s['name']}: {s['description']}" for s in skills]
        return ToolResult.ok("\n".join(lines), count=len(skills), skills=skills)


@tool
class SkillRead(Tool):
    name = "skill_read"
    description = (
        "Read full content (Level 1) of a skill by name. "
        "Call this when you want to apply a skill you saw in the summary."
    )
    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    read_only = True
    tags = ["skills"]

    async def run(self, name: str) -> ToolResult:
        sf = _skills_dir(self.config.home) / name / "SKILL.md"
        if not sf.exists():
            return ToolResult.err(f"Skill not found: {name}")
        text = sf.read_text(encoding="utf-8")
        return ToolResult.ok(text, name=name, path=str(sf))


@tool
class SkillManage(Tool):
    name = "skill_manage"
    description = (
        "Create or update a skill. Skills are reusable markdown documents "
        "that capture procedures, gotchas, and patterns. "
        "After solving a non-trivial task, CONSIDER creating a skill so "
        "future you can repeat the success. "
        "Action: 'create' to write a new skill, 'update' to revise, "
        "'delete' to remove."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "update", "delete"]},
            "name": {"type": "string", "description": "Skill name (kebab-case, e.g. 'deploy-nextjs-vercel')."},
            "content": {"type": "string", "description": "Full markdown content. Required for create/update."},
            "description": {"type": "string", "description": "One-line description. Required for create."},
        },
        "required": ["action", "name"],
    }
    tags = ["skills", "self-improvement"]

    async def run(self, action: str, name: str,
                  content: str = "", description: str = "") -> ToolResult:
        sd = _skills_dir(self.config.home)
        skill_dir = sd / name
        sf = skill_dir / "SKILL.md"

        if action == "create":
            if sf.exists():
                return ToolResult.err(f"Skill '{name}' already exists. Use action='update'.")
            if not content:
                return ToolResult.err("content required for create")
            skill_dir.mkdir(parents=True, exist_ok=True)
            full = f"# {name}\n\n{description}\n\n{content}\n"
            sf.write_text(full, encoding="utf-8")
            return ToolResult.ok(f"Created skill '{name}' at {sf}",
                                 name=name, path=str(sf))

        elif action == "update":
            if not sf.exists():
                return ToolResult.err(f"Skill '{name}' does not exist. Use action='create'.")
            if not content:
                return ToolResult.err("content required for update")
            sf.write_text(content, encoding="utf-8")
            return ToolResult.ok(f"Updated skill '{name}' at {sf}",
                                 name=name, path=str(sf))

        elif action == "delete":
            if not sf.exists():
                return ToolResult.err(f"Skill '{name}' does not exist.")
            import shutil
            shutil.rmtree(skill_dir)
            return ToolResult.ok(f"Deleted skill '{name}'")

        return ToolResult.err(f"Unknown action: {action}")
