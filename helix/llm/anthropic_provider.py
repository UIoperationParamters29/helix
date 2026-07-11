"""Anthropic Claude provider (native SDK, not OpenAI-compat shim)."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from .base import LLM, LLMChunk, LLMResponse, _resolve_api_key


class AnthropicLLM(LLM):
    """Native Anthropic SDK — supports Claude 3.5/3.7/4 models with tool use."""

    def __init__(self, config):
        super().__init__(config)
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=_resolve_api_key("anthropic", config))

    async def complete(self, messages: list[dict], tools: list[dict] | None = None,
                       system: str | None = None) -> LLMResponse:
        # Convert OpenAI-style messages to Anthropic format
        msgs = self._convert_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [{
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            } for t in tools]

        try:
            resp = await self.client.messages.create(**kwargs)
        except Exception as e:
            return LLMResponse(content="", finish_reason="error",
                               usage={}, raw={"error": str(e)})

        content = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "args": block.input if isinstance(block.input, dict) else {},
                })
        usage = {
            "prompt": resp.usage.input_tokens,
            "completion": resp.usage.output_tokens,
            "total": resp.usage.input_tokens + resp.usage.output_tokens,
        }
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=usage,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )

    async def stream(self, messages: list[dict], tools: list[dict] | None = None,
                     system: str | None = None) -> AsyncIterator[LLMChunk]:
        # For simplicity, fall back to non-streaming and yield once
        # (full streaming with tool_calls is complex; can be improved later)
        resp = await self.complete(messages, tools, system)
        if resp.content:
            yield LLMChunk(content=resp.content, finish_reason=None)
        for tc in resp.tool_calls:
            yield LLMChunk(
                tool_call_delta={"id": tc["id"], "name": tc["name"],
                                 "args_fragment": json.dumps(tc["args"])},
                finish_reason=None,
            )
        yield LLMChunk(content="", finish_reason=resp.finish_reason)

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """OpenAI message format -> Anthropic format."""
        out = []
        for m in messages:
            role = m["role"]
            if role == "system":
                continue  # handled separately
            if role == "tool":
                # Anthropic expects tool_result blocks
                out.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m["content"],
                    }],
                })
            elif role == "assistant" and m.get("tool_calls"):
                # Convert to tool_use blocks
                content = []
                if m.get("content"):
                    content.append({"type": "text", "text": m["content"]})
                for tc in m["tool_calls"]:
                    try:
                        args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                    except Exception:
                        args = {}
                    content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": args,
                    })
                out.append({"role": "assistant", "content": content})
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out
