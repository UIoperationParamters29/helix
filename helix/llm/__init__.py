"""LLM provider abstraction.

Single interface; multiple backends. Supports:
  - openai    (OpenAI official API)
  - anthropic (Claude)
  - zai       (Z.ai GLM)
  - ollama    (local)
  - lmstudio  (local)
  - custom    (any OpenAI-compatible endpoint)

All return a unified Stream of LLMChunk objects.
"""
# Import order matters: base defines the factory; concrete providers register themselves.
from .base import LLM, LLMChunk, LLMResponse, get_llm  # noqa: F401
from .openai_compat import OpenAICompatLLM  # noqa: F401
from .anthropic_provider import AnthropicLLM  # noqa: F401

__all__ = ["LLM", "LLMChunk", "LLMResponse", "get_llm",
           "OpenAICompatLLM", "AnthropicLLM"]
