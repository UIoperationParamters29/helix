"""HELIX — Hierarchical Executive Loop for Intelligent eXecution.

A self-improving, phone-native agent harness. Synthesizes:
- Hermes: skills + agent-owned learning + progressive disclosure
- OpenHands: event-sourced conversation log + stateless agent
- OpenClaw: plugin SDK + harness registry + tool policy
- SWE-agent: deliberate Agent-Computer Interface design
- Termux + self-ADB: full phone control without root
"""
from .config import HelixConfig, get_helix_home, get_config

__version__ = "0.1.0"
__all__ = ["HelixConfig", "get_helix_home", "get_config", "__version__"]
