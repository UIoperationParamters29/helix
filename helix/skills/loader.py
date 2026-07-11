"""Skill discovery + Level-0 summaries."""
from __future__ import annotations
from pathlib import Path


def load_skill_summaries(home: Path) -> list[dict]:
    """Return Level-0 info for every skill in HELIX_HOME/skills/."""
    import re
    skills = []
    sd = home / "skills"
    if not sd.exists():
        return skills
    for d in sorted(sd.iterdir()):
        if not d.is_dir():
            continue
        sf = d / "SKILL.md"
        if not sf.exists():
            continue
        try:
            text = sf.read_text(encoding="utf-8")
            title = d.name
            m = re.match(r"^#\s+(.+)$", text, re.M)
            if m:
                title = m.group(1).strip()
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


def load_skill_summaries_for_prompt(home: Path) -> list[dict]:
    """Alias for clarity."""
    return load_skill_summaries(home)
