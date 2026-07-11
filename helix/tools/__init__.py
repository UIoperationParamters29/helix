"""Tool system — self-registering registry.

Each tool is a single file with a @tool decorator. New tool = one new file.
No central __all__ list to maintain. This pattern stolen from Hermes.
"""
# Import base first (defines registry + decorator)
from .base import Tool, ToolResult, tool, get_registry, all_tools, get_tool, ToolExecutor

# Explicitly import all tool modules to trigger @tool registration.
# This is more reliable than pkgutil iteration at import time.
from . import bash        # noqa: F401
from . import file         # noqa: F401
from . import web          # noqa: F401
from . import skill_manage # noqa: F401
from . import memory       # noqa: F401
# Phone subpackage — each module registers its own tools
from .phone import sms, call, notification, camera, location, clipboard  # noqa: F401
from .phone import hardware, tts, ui, apps  # noqa: F401

__all__ = ["Tool", "ToolResult", "tool", "get_registry", "all_tools", "get_tool", "ToolExecutor"]
