"""LLM provider abstraction.

Single interface; multiple backends. Supports:
  - openai    (OpenAI official API)
  - anthropic (Claude) — OPTIONAL, requires `pip install -e ".[anthropic]"`
  - zai       (Z.ai GLM)
  - ollama    (local)
  - lmstudio  (local)
  - custom    (any OpenAI-compatible endpoint)

All return a unified Stream of LLMChunk objects.
"""
# Import order matters: base defines the factory; concrete providers register themselves.
from .base import LLM, LLMChunk, LLMResponse, get_llm  # noqa: F401
from .openai_compat import OpenAICompatLLM  # noqa: F401

# Anthropic is optional — don't fail the whole package import if it's missing.
try:
    from .anthropic_provider import AnthropicLLM  # noqa: F401
except ImportError:
    AnthropicLLM = None  # type: ignore[assignment,misc]

__all__ = ["LLM", "LLMChunk", "LLMResponse", "get_llm",
           "OpenAICompatLLM", "AnthropicLLM"]
