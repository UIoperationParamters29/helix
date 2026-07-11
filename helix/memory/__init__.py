"""Memory manager — load/save MEMORY.md, USER.md, IDENTITY.md."""
from .manager import load_memory, load_memory_for_prompt, init_memory_files

__all__ = ["load_memory", "load_memory_for_prompt", "init_memory_files"]
