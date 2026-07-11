"""Workspace base."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from ..config import HelixConfig


class Workspace(ABC):
    """Where commands run."""

    def __init__(self, config: HelixConfig):
        self.config = config

    @abstractmethod
    async def execute(self, command: str, timeout: int = 30, cwd: str | None = None) -> tuple[int, str]:
        ...

    @property
    @abstractmethod
    def kind(self) -> str: ...


def get_workspace(config: HelixConfig | None = None) -> Workspace:
    cfg = config or HelixConfig.load()
    if cfg.on_termux:
        return TermuxWorkspace(cfg)
    return LocalWorkspace(cfg)
