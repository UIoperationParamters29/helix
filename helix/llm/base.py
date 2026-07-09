"""LLM base — the provider-agnostic interface."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from ..config import HelixConfig


@dataclass
class LLMChunk:
    """One streaming chunk."""
    content: str = ""
    tool_call_delta: dict[str, Any] | None = None  # partial tool_call
    finish_reason: str | None = None


@dataclass
class LLMResponse:
    """Full non-streaming response."""
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


class LLM(ABC):
    """Provider-agnostic LLM interface."""

    def __init__(self, config: HelixConfig):
        self.config = config

    @abstractmethod
    async def complete(self, messages: list[dict], tools: list[dict] | None = None,
                       system: str | None = None) -> LLMResponse:
        """Single completion."""
        ...

    @abstractmethod
    async def stream(self, messages: list[dict], tools: list[dict] | None = None,
                     system: str | None = None) -> AsyncIterator[LLMChunk]:
        """Streaming completion."""
        ...
        # make it an async generator
        yield LLMChunk()  # pragma: no cover

    @property
    def model_name(self) -> str:
        return self.config.model


def get_llm(config: HelixConfig | None = None) -> LLM:
    """Factory: pick provider based on config."""
    if config is None:
        from ..config import get_config
        config = get_config()

    provider = (config.provider or "openai").lower()

    # Lazy import to avoid circular dependency
    from .openai_compat import OpenAICompatLLM
    from .anthropic_provider import AnthropicLLM

    # All OpenAI-compatible endpoints go through OpenAICompatLLM
    if provider in ("openai", "zai", "ollama", "lmstudio", "custom"):
        return OpenAICompatLLM(config)
    elif provider == "anthropic":
        return AnthropicLLM(config)
    else:
        # Default: assume OpenAI-compatible
        return OpenAICompatLLM(config)


def _resolve_base_url(provider: str, config: HelixConfig) -> str | None:
    """Provider-specific base URL defaults."""
    if config.base_url:
        return config.base_url
    if provider == "zai":
        return "https://open.bigmodel.cn/api/paas/v4"
    if provider == "ollama":
        return "http://localhost:11434/v1"
    if provider == "lmstudio":
        return "http://localhost:1234/v1"
    return None  # OpenAI default


def _resolve_api_key(provider: str, config: HelixConfig) -> str:
    """Provider-specific env var fallbacks."""
    if config.api_key:
        return config.api_key
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "zai": "ZAI_API_KEY",
        "ollama": "OLLAMA_API_KEY",
        "lmstudio": "LMSTUDIO_API_KEY",
    }
    return os.environ.get(env_map.get(provider, "OPENAI_API_KEY"), "")
