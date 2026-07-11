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
            # Capture rich error detail so conversation.py can surface it to the UI
            err_str = str(e)
            status = getattr(e, "status_code", None)
            # OpenAI SDK v1+: APIStatusError has .response with the httpx.Response
            try:
                resp_obj = getattr(e, "response", None)
                if resp_obj is not None and hasattr(resp_obj, "text"):
                    body_text = resp_obj.text
                    err_str = f"{err_str} | body={body_text}"
                    if status is None:
                        status = getattr(resp_obj, "status_code", None)
                else:
                    body = getattr(e, "body", None)
                    if body is not None:
                        if isinstance(body, (dict, list)):
                            import json as _json
                            err_str = f"{err_str} | body={_json.dumps(body)}"
                        else:
                            err_str = f"{err_str} | body={body}"
            except Exception:
                pass
            base = self.client.base_url
            # Build a contextual hint based on status code
            hint = ""
            if status == 404:
                hint = ("404 = wrong URL. Most gateways need a /v1 suffix. "
                        "Try: export HELIX_BASE_URL=" + str(base).rstrip('/') + "/v1")
            elif status == 401:
                hint = "401 = bad API key. Check HELIX_API_KEY."
            elif status == 400:
                hint = ("400 = bad request. Usually means HELIX_MODEL doesn't exist on this gateway, "
                        "or the gateway rejected the request format. Check the body above.")
            elif status == 402 or status == 403:
                hint = ("402/403 = billing/permission. The gateway accepted your key but the upstream "
                        "provider rejected the call (e.g. insufficient credits). Add credits at the upstream provider.")
            elif status and status >= 500:
                hint = ("5xx = gateway/upstream error. The gateway is up but the upstream model provider "
                        "failed (e.g. rate limit, outage, billing). Try a different model or wait.")
            return LLMResponse(
                content="",
                finish_reason="error",
                usage={},
                raw={
                    "error": err_str,
                    "status": status,
                    "url": f"{base}chat/completions",
                    "model": self.config.model,
                    "hint": hint,
                },
            )

        # Some gateways return 200 OK with no choices (rare but happens on
        # content-filter or upstream errors). Handle gracefully.
        if not resp.choices:
            # Try to extract the gateway's error message from the response body
            raw_dump = resp.model_dump() if hasattr(resp, "model_dump") else {}
            inner_err = ""
            if isinstance(raw_dump, dict):
                # Many gateways put the error in a top-level "error" field
                err_field = raw_dump.get("error")
                if isinstance(err_field, dict):
                    inner_err = err_field.get("message", "") or str(err_field)
                elif isinstance(err_field, str):
                    inner_err = err_field
            err_msg = inner_err or "LLM returned 200 but no choices (gateway may have filtered or upstream failed)"
            # Detect common patterns and add hints
            hint = ""
            err_lower = inner_err.lower() if inner_err else ""
            if "credit" in err_lower or "insufficient_funds" in err_lower or "billing" in err_lower:
                hint = ("The gateway accepted your request but the upstream provider (Vercel/OpenAI/etc) "
                        "says you have no credits. Add credits at the upstream provider, or switch to a "
                        "different HELIX_MODEL that doesn't require credits.")
            elif "rate" in err_lower and "limit" in err_lower:
                hint = "Rate limited. Wait a minute and try again."
            elif "model" in err_lower and ("not" in err_lower or "unknown" in err_lower or "invalid" in err_lower):
                hint = ("Model name not recognized by gateway. Check your gateway's model list and "
                        "set HELIX_MODEL to the exact name (e.g. gpt-4o-mini, claude-3-5-sonnet, glm-4).")
            return LLMResponse(
                content="",
                finish_reason="error",
                usage={},
                raw={
                    "error": err_msg,
                    "status": 200,  # gateway returned 200, but no choices
                    "url": f"{self.client.base_url}chat/completions",
                    "model": self.config.model,
                    "hint": hint or "Gateway returned 200 OK but with no choices. Check the error field above.",
                    "raw_response": raw_dump,
                },
            )
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
