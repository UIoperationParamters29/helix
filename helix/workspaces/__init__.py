"""Workspace abstraction — where commands actually execute.

Three implementations:
  - LocalWorkspace:    runs on the host directly (PC or Termux)
  - TermuxWorkspace:   detects Termux + sets up android-tools, termux-api
  - DockerWorkspace:   (stub) for sandboxed execution on PC
"""
from .base import Workspace, get_workspace
from .local import LocalWorkspace
from .termux import TermuxWorkspace

__all__ = ["Workspace", "get_workspace", "LocalWorkspace", "TermuxWorkspace"]
