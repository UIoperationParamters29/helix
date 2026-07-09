"""OpenAI-compatible LLM provider.

Works with: OpenAI, Z.ai (GLM), Ollama, LM Studio, vLLM, LiteLLM proxy,
and any endpoint that speaks the OpenAI Chat Completions API.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from .base import LLM, LLMChunk, LLMResponse, _resolve_base_url, _resolve_api_key


class OpenAICompatLLM(LLM):
    """OpenAI-compatible chat completions + tool calling."""

    def __init__(self, config):
        super().__init__(config)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=_resolve_api_key(config.provider, config) or "sk-nokey",
            base_url=_resolve_base_url(config.provider, config),
        )

    async def complete(self, messages: list[dict], tools: list[dict] | None = None,
                       system: str | None = None) -> LLMResponse:
        msgs = self._build_messages(messages, system)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if tools:
            kwargs["tools"] = [{
                "type": "function",
                "function": t,
            } for t in tools]
            kwargs["tool_choice"] = "auto"

        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            return LLMResponse(content="", finish_reason="error",
                               usage={}, raw={"error": str(e)})

        choice = resp.choices[0]
        msg = choice.message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"_raw": tc.function.arguments}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": args,
                })
        usage = {}
        if resp.usage:
            usage = {
                "prompt": resp.usage.prompt_tokens,
                "completion": resp.usage.completion_tokens,
                "total": resp.usage.total_tokens,
            }
        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )

    async def stream(self, messages: list[dict], tools: list[dict] | None = None,
                     system: str | None = None) -> AsyncIterator[LLMChunk]:
        msgs = self._build_messages(messages, system)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self.client.chat.completions.create(**kwargs)
        except Exception as e:
            yield LLMChunk(content=f"[LLM error: {e}]", finish_reason="error")
            return

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            tc_delta = None
            if delta.tool_calls:
                tc = delta.tool_calls[0]
                tc_delta = {
                    "id": tc.id,
                    "name": tc.function.name if tc.function else None,
                    "args_fragment": tc.function.arguments if tc.function else "",
                }
            yield LLMChunk(
                content=delta.content or "",
                tool_call_delta=tc_delta,
                finish_reason=chunk.choices[0].finish_reason,
            )

    def _build_messages(self, messages: list[dict], system: str | None) -> list[dict]:
        """Prepend system prompt if given."""
        out = []
        if system:
            out.append({"role": "system", "content": system})
        out.extend(messages)
        return out
