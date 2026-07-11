"""Tool base class + registry.

Design:
- Tool = name, description, JSON schema for args, async handler.
- @tool decorator registers at import time.
- Tools live in helix/tools/<name>.py — importing the package auto-loads all.
- Before/after hooks enable policy enforcement (security, logging, approval).
"""
from __future__ import annotations

import inspect, re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from ..config import HelixConfig


@dataclass
class ToolResult:
    """Standardized tool return."""
    output: str
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, *args, **kwargs) -> "ToolResult":
        """Create a success result.

        Usage: ToolResult.ok("output text", key1=val1, key2=val2)
        The first positional arg is the output text. Any kwargs go into metadata.
        If 'output' is passed as a kwarg, it's ignored (use positional).
        """
        output = args[0] if args else kwargs.pop("output", "")
        kwargs.pop("output", None)  # drop any stray output kwarg
        return cls(output=output, is_error=False, metadata=kwargs)

    @classmethod
    def err(cls, *args, **kwargs) -> "ToolResult":
        output = args[0] if args else kwargs.pop("output", "")
        kwargs.pop("output", None)
        return cls(output=output, is_error=True, metadata=kwargs)


class Tool(ABC):
    """Base tool class. Subclass + implement run()."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}        # JSON schema for args
    dangerous: bool = False                # requires approval
    read_only: bool = False                # safe to auto-approve
    tags: list[str] = []                   # for grouping (filesystem, web, phone, ...)

    def __init__(self, config: HelixConfig | None = None):
        self.config = config or HelixConfig()

    @abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        ...

    def to_schema(self) -> dict[str, Any]:
        """OpenAI tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters or {"type": "object", "properties": {}},
        }

    def check_dangerous(self, args: dict) -> bool:
        """Hook for per-call danger assessment."""
        return self.dangerous


# --- Global registry ---
_REGISTRY: dict[str, type[Tool]] = {}


def tool(cls: type[Tool]) -> type[Tool]:
    """Decorator: register a tool class."""
    if not cls.name:
        cls.name = cls.__name__.lower().replace("tool", "")
    if cls.name in _REGISTRY:
        # Allow re-import to update
        pass
    _REGISTRY[cls.name] = cls
    return cls


def get_registry() -> dict[str, type[Tool]]:
    return dict(_REGISTRY)


def all_tools(config: HelixConfig | None = None) -> list[Tool]:
    """Instantiate all registered tools."""
    cfg = config or HelixConfig()
    return [cls(cfg) for cls in _REGISTRY.values()]


def get_tool(name: str, config: HelixConfig | None = None) -> Tool | None:
    """Instantiate a single tool by name."""
    cls = _REGISTRY.get(name)
    return cls(config) if cls else None


# --- Before/after hooks ---
BeforeHook = Callable[[Tool, dict], Awaitable[bool | str]]   # False=deny, True=allow, str=reason
AfterHook = Callable[[Tool, dict, ToolResult], Awaitable[None]]


class ToolExecutor:
    """Runs tools with policy + hooks."""

    def __init__(self, config: HelixConfig | None = None):
        self.config = config or HelixConfig()
        self.before_hooks: list[BeforeHook] = []
        self.after_hooks: list[AfterHook] = []
        self._instances: dict[str, Tool] = {}

    def _get_instance(self, name: str) -> Tool | None:
        if name not in self._instances:
            t = get_tool(name, self.config)
            if t is None:
                return None
            self._instances[name] = t
        return self._instances[name]

    async def execute(self, name: str, args: dict) -> ToolResult:
        """Execute a tool with full hook + policy enforcement."""
        t = self._get_instance(name)
        if t is None:
            return ToolResult.err(f"Unknown tool: {name}")

        # Danger check
        if t.check_dangerous(args) and not self.config.auto_approve_writes:
            return ToolResult.err(
                f"Tool '{name}' is marked dangerous and auto_approve_writes=False. "
                f"Approve via UI first."
            )

        # Before hooks
        for hook in self.before_hooks:
            decision = await hook(t, args)
            if decision is False:
                return ToolResult.err(f"Tool '{name}' denied by policy hook")
            if isinstance(decision, str):
                return ToolResult.err(f"Tool '{name}' denied: {decision}")

        # Execute
        try:
            result = await t.run(**args)
        except TypeError as e:
            return ToolResult.err(f"Bad arguments to '{name}': {e}")
        except Exception as e:
            return ToolResult.err(f"Tool '{name}' raised: {type(e).__name__}: {e}")

        # After hooks
        for hook in self.after_hooks:
            try:
                await hook(t, args, result)
            except Exception:
                pass  # hooks must not break the flow

        return result


# Auto-import all tool modules so @tool runs at import time
def _autoload():
    """Import all tool modules to trigger @tool registration."""
    import importlib, pkgutil, sys
    base = __name__.rsplit(".", 1)[0]
    pkg = sys.modules[__name__]
    if not hasattr(pkg, "__path__"):
        return
    # Top-level tools
    for finder, name, ispkg in pkgutil.iter_modules(pkg.__path__):
        if name.startswith("_") or ispkg:
            continue
        try:
            importlib.import_module(f"{base}.{name}")
        except Exception:
            pass  # tool may fail to import on certain platforms (e.g. phone tools on PC)
    # phone subpackage
    try:
        phone_pkg = importlib.import_module(f"{base}.phone")
        if hasattr(phone_pkg, "__path__"):
            for finder, name, ispkg in pkgutil.iter_modules(phone_pkg.__path__):
                if name.startswith("_"):
                    continue
                try:
                    importlib.import_module(f"{base}.phone.{name}")
                except Exception:
                    pass
    except Exception:
        pass
