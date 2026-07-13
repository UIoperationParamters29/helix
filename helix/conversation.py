"""Conversation — the agent loop. Owns state, drives the LLM, manages context.

This is the core of HELIX. Key design decisions (learned from OpenHands + Hermes):

1. CONTEXT MANAGEMENT: Instead of crude truncation (last 50 events), we use
   a sliding window that ALWAYS keeps the original user request + a running
   summary of what's been done + the last N observations. This prevents the
   agent from forgetting the task mid-way through.

2. STUCK DETECTION: Track (tool, args_hash) pairs. If the same call is made
   3 times with the same result, inject a "you're stuck" message and force
   the agent to try a different approach.

3. TOKEN AWARENESS: Estimate token count (chars/4). When approaching the
   context limit, condense older observations into a summary.

4. TASK TRACKING: Maintain a "task state" that reminds the agent what it's
   doing. Injected into every LLM call so it never forgets the goal.

5. REAL STREAMING: The streaming version actually yields content as it
   arrives from the LLM, not all at once at the end.
"""
from __future__ import annotations

import asyncio, json, time, uuid, hashlib
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from .config import HelixConfig
from .events import (
    Event, MessageEvent, ActionEvent, ObservationEvent,
    AgentErrorEvent, CondensationEvent, ApprovalEvent, FinishEvent,
    event_from_dict,
)
from .llm import get_llm, LLM
from .tools import ToolExecutor, all_tools
from .text_utils import clean_for_llm, strip_ansi
from .skills.loader import load_skill_summaries_for_prompt
from .memory.manager import load_memory_for_prompt


class Conversation:
    """Owns ConversationState + EventLog. Drives the agent loop."""

    def __init__(self, config: HelixConfig | None = None,
                 session_id: str | None = None,
                 llm: LLM | None = None,
                 executor: ToolExecutor | None = None):
        self.config = config or HelixConfig.load()
        self.session_id = session_id or uuid.uuid4().hex[:16]
        self.llm = llm or get_llm(self.config)
        self.executor = executor or ToolExecutor(self.config)
        self.events: list[Event] = []
        self._listeners: list[Callable[[Event], None]] = []
        self._approval_queue: dict[str, asyncio.Future] = {}
        self._session_file: Path = self.config.home / "sessions" / f"{self.session_id}.jsonl"

        # Build tool schemas (called once)
        self._tool_schemas = [t.to_schema() for t in all_tools(self.config)]
        self._tools_by_name = {t.name: t for t in all_tools(self.config)}

        # Context management state
        self._system_prompt: str | None = None  # cached, rebuilt only when needed
        self._call_history: list[str] = []  # hashes of (tool, args) for stuck detection
        self._task_summary: str = ""  # running summary of what's been done
        self._original_request: str = ""  # the user's original request (always kept)

    # --- Event log ---
    def append(self, event: Event) -> None:
        self.events.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass
        try:
            with open(self._session_file, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception:
            pass

    def add_listener(self, fn: Callable[[Event], None]) -> None:
        self._listeners.append(fn)

    def load_history(self) -> None:
        if not self._session_file.exists():
            return
        self.events = []
        for line in self._session_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                self.events.append(event_from_dict(d))
            except Exception:
                continue

    # --- System prompt (cached) ---
    def _get_system_prompt(self) -> str:
        """Build and cache the system prompt. Only rebuilt if not cached."""
        if self._system_prompt is None:
            self._system_prompt = self._build_system_prompt()
        return self._system_prompt

    def _build_system_prompt(self) -> str:
        mem = load_memory_for_prompt(self.config.home)
        skills = load_skill_summaries_for_prompt(self.config.home) if self.config.skills_enabled else []

        identity = mem.get("IDENTITY") or self._default_identity()
        user_facts = mem.get("USER", "")
        memory = mem.get("MEMORY", "")

        skills_block = ""
        if skills:
            skills_block = "\n## Available skills\nCall `skill_read` to load full content.\n"
            for s in skills[:20]:  # cap at 20 skills to save context
                skills_block += f"- **{s['name']}**: {s['description']}\n"

        platform = self._platform_context()

        return f"""# {self.config.persona}

{identity}

## User
{user_facts or "(learn about the user via conversation)"}

## Memory
{memory or "(no persistent notes yet)"}
{skills_block}

## Platform: {platform}
## Tools: {len(self._tool_schemas)} available

## Rules
1. BE EFFICIENT. Minimize tool calls. Think before acting.
2. DON'T REPEAT. If a tool fails or returns "no matches" twice, change approach.
3. READ OUTPUTS. Tool output is in your context — don't re-fetch it.
4. MAX 12 tool calls per task. If stuck, summarize and ask the user.
5. Be concise. No filler. Act, verify, report.

## Phone UI rules (if on Termux)
- phone_ui_dump returns XML in the output. Parse it for bounds="[x1,y1][x2,y2]".
- Tap center: ((x1+x2)/2, (y1+y2)/2). Don't tap randomly.
- After tapping, dump again to see what changed.
- NEVER use file_search/file_read on UI dump files — the content is already in your context.
"""

    def _default_identity(self) -> str:
        return (
            "You are HELIX, a self-improving agent running on the user's device. "
            "You execute shell commands, edit files, browse the web, and on phones: "
            "control the UI via ADB. You learn from each task and write skills for reuse."
        )

    def _platform_context(self) -> str:
        import platform as plat
        if self.config.on_termux:
            return f"Termux/Android (aarch64)"
        return f"{plat.system()}/{plat.machine()}"

    # --- Context management (THE KEY FIX) ---
    def _build_messages(self) -> list[dict]:
        """Build messages for the LLM with smart context management.

        Instead of crude truncation (last 50 events), we:
        1. ALWAYS keep the original user request first
        2. Include a running summary of what's been done
        3. Include the last N tool calls + observations (recent context)
        4. Estimate token count and condense if needed
        """
        msgs = []

        # 1. Always include original request
        if self._original_request:
            msgs.append({"role": "user", "content": self._original_request})

        # 2. Include task summary (what's been done so far)
        if self._task_summary:
            msgs.append({"role": "system", "content": f"Progress so far:\n{self._task_summary}"})

        # 3. Collect recent events (skip system/condensation/finish)
        recent_events = []
        for e in reversed(self.events):
            if isinstance(e, (CondensationEvent, ApprovalEvent, FinishEvent)):
                continue
            recent_events.insert(0, e)

        # 4. Estimate token count and trim if needed
        # Target: ~80k chars (~20k tokens) for recent context
        MAX_CONTEXT_CHARS = 80000
        current_chars = sum(len(json.dumps(m)) for m in msgs)
        trimmed_events = []

        for e in reversed(recent_events):
            event_msg = e.to_message()
            event_chars = len(json.dumps(event_msg))
            if current_chars + event_chars > MAX_CONTEXT_CHARS:
                break
            trimmed_events.insert(0, e)
            current_chars += event_chars

        # 5. Convert to messages
        for e in trimmed_events:
            msg = e.to_message()
            # Truncate large tool outputs in observations
            if isinstance(e, ObservationEvent):
                content = msg.get("content", "")
                if len(content) > 4000:
                    msg["content"] = content[:2000] + f"\n[...truncated {len(content)-4000} chars...]\n" + content[-2000:]
            msgs.append(msg)

        return msgs

    def _update_task_summary(self, event: Event) -> None:
        """Maintain a running summary of actions taken."""
        if isinstance(event, ActionEvent):
            # Keep last 10 actions in summary
            summary_line = f"  {len(self._call_history)}. {event.tool}({_truncate_args(event.args)})"
            if not self._task_summary:
                self._task_summary = summary_line
            else:
                lines = self._task_summary.splitlines()
                lines.append(summary_line)
                # Keep only last 15 lines
                self._task_summary = "\n".join(lines[-15:])

    def _check_stuck(self, tool: str, args: dict) -> bool:
        """Detect if the agent is repeating the same action."""
        args_hash = hashlib.md5(json.dumps(args, sort_keys=True, default=str).encode()).hexdigest()[:8]
        call_key = f"{tool}:{args_hash}"
        self._call_history.append(call_key)

        # Check if this exact call was made 3+ times
        count = self._call_history.count(call_key)
        return count >= 3

    # --- Main loop ---
    async def send(self, user_text: str) -> AsyncIterator[Event]:
        """Send a user message and stream the agent's response."""
        from .notifications import start_task_notification, update_task_notification, end_task_notification

        await start_task_notification(f"Processing: {user_text[:80]}")

        # Store original request for context management
        self._original_request = user_text

        user_evt = MessageEvent(role="user", content=user_text)
        self.append(user_evt)
        yield user_evt

        system = self._get_system_prompt()
        stuck_warning_count = 0

        for iteration in range(self.config.max_iterations):
            # Build context-managed messages
            messages = self._build_messages()

            # Inject stuck warning if needed
            if stuck_warning_count > 0:
                messages.append({"role": "system", "content":
                    f"WARNING: You've repeated the same action {stuck_warning_count + 2} times. "
                    f"You are stuck. Try a completely different approach or summarize what you've "
                    f"done and ask the user for help."})

            # Inject progress reminder at 80% of max iterations
            if iteration >= self.config.max_iterations * 0.8:
                messages.append({"role": "system", "content":
                    f"You've made {len(self._call_history)} tool calls (max {self.config.max_iterations}). "
                    f"Wrap up now — either complete the task or summarize what you've done."})

            # Call LLM
            try:
                resp = await self.llm.complete(messages=messages, tools=self._tool_schemas, system=system)
            except Exception as e:
                err = AgentErrorEvent(message=f"LLM error: {type(e).__name__}: {e}")
                self.append(err)
                yield err
                await end_task_notification("Error")
                return

            if resp.finish_reason == "error":
                err_detail = ""
                if isinstance(resp.raw, dict):
                    err_detail = str(resp.raw.get("error", ""))[:500]
                    if resp.raw.get("hint"):
                        err_detail += f"\nHint: {resp.raw['hint']}"
                else:
                    err_detail = resp.content or "Unknown error"
                err = AgentErrorEvent(message=f"LLM error: {err_detail}")
                self.append(err)
                yield err
                await end_task_notification("Error")
                return

            # Tool calls
            if resp.tool_calls:
                if resp.content:
                    thought = MessageEvent(role="assistant", content=resp.content)
                    self.append(thought)
                    yield thought

                for tc in resp.tool_calls:
                    action = ActionEvent(
                        tool=tc["name"],
                        args=tc.get("args", {}),
                        thought=resp.content or "",
                    )
                    action.id = tc.get("id", action.id)
                    self.append(action)
                    yield action
                    self._update_task_summary(action)

                    # Update notification
                    await update_task_notification(f"[{iteration+1}] {tc['name']}...")

                    # Stuck detection
                    if self._check_stuck(tc["name"], tc.get("args", {})):
                        stuck_warning_count += 1

                    # Execute
                    result = await self.executor.execute(tc["name"], tc.get("args", {}))
                    cleaned_output = clean_for_llm(result.output)
                    obs = ObservationEvent(
                        action_id=action.id,
                        tool=tc["name"],
                        output=cleaned_output,
                        is_error=result.is_error,
                        metadata=result.metadata,
                    )
                    self.append(obs)
                    yield obs
                continue
            else:
                # Done — assistant responded with text
                cleaned_content = strip_ansi(resp.content or "")
                msg = MessageEvent(role="assistant", content=cleaned_content)
                self.append(msg)
                yield msg
                finish = FinishEvent(reason="completed")
                self.append(finish)
                yield finish
                await end_task_notification(cleaned_content[:80] if cleaned_content else "Done")
                return

        # Hit iteration cap
        err = AgentErrorEvent(
            message=f"Reached max tool calls ({self.config.max_iterations}). "
                    f"Task may be incomplete. Summary:\n{self._task_summary}"
        )
        self.append(err)
        yield err
        finish = FinishEvent(reason="max_iterations")
        self.append(finish)
        yield finish
        await end_task_notification("Max calls reached")

    # --- Streaming version ---
    async def send_streaming(self, user_text: str) -> AsyncIterator[Event]:
        """Stream assistant text token-by-token."""
        from .text_utils import clean_for_llm, strip_ansi
        from .notifications import start_task_notification, update_task_notification, end_task_notification

        await start_task_notification(f"Processing: {user_text[:80]}")
        self._original_request = user_text

        user_evt = MessageEvent(role="user", content=user_text)
        self.append(user_evt)
        yield user_evt

        system = self._get_system_prompt()
        stuck_warning_count = 0

        for iteration in range(self.config.max_iterations):
            messages = self._build_messages()

            if stuck_warning_count > 0:
                messages.append({"role": "system", "content":
                    f"WARNING: You've repeated the same action. Try a different approach."})

            if iteration >= self.config.max_iterations * 0.8:
                messages.append({"role": "system", "content":
                    f"You've made {len(self._call_history)} tool calls. Wrap up now."})

            try:
                collected_content = ""
                collected_tool_calls: list[dict] = []
                current_tc: dict | None = None
                tc_args_buffer: dict[str, str] = {}

                async for chunk in self.llm.stream(messages=messages, tools=self._tool_schemas, system=system):
                    if chunk.content:
                        collected_content += chunk.content
                        # Yield streaming content immediately
                        yield MessageEvent(role="assistant", content=collected_content)
                    if chunk.tool_call_delta:
                        d = chunk.tool_call_delta
                        if d.get("id") and d.get("name"):
                            if current_tc:
                                try:
                                    current_tc["args"] = json.loads(tc_args_buffer.get(current_tc["id"], "")) if tc_args_buffer.get(current_tc["id"]) else {}
                                except Exception:
                                    current_tc["args"] = {"_raw": tc_args_buffer.get(current_tc["id"], "")}
                                collected_tool_calls.append(current_tc)
                            current_tc = {"id": d["id"], "name": d["name"]}
                            tc_args_buffer[d["id"]] = ""
                        if d.get("args_fragment") and current_tc:
                            tc_args_buffer[current_tc["id"]] = tc_args_buffer.get(current_tc["id"], "") + d["args_fragment"]
                    if chunk.finish_reason:
                        if current_tc:
                            try:
                                current_tc["args"] = json.loads(tc_args_buffer.get(current_tc["id"], "")) if tc_args_buffer.get(current_tc["id"]) else {}
                            except Exception:
                                current_tc["args"] = {"_raw": tc_args_buffer.get(current_tc["id"], "")}
                            collected_tool_calls.append(current_tc)
                            current_tc = None
                        break

                if collected_tool_calls:
                    if collected_content:
                        messages.append({"role": "assistant", "content": collected_content})

                    for tc in collected_tool_calls:
                        action = ActionEvent(
                            tool=tc["name"],
                            args=tc.get("args", {}),
                            thought=collected_content,
                        )
                        action.id = tc.get("id", action.id)
                        self.append(action)
                        yield action
                        self._update_task_summary(action)
                        await update_task_notification(f"[{iteration+1}] {tc['name']}...")

                        if self._check_stuck(tc["name"], tc.get("args", {})):
                            stuck_warning_count += 1

                        result = await self.executor.execute(tc["name"], tc.get("args", {}))
                        cleaned_output = clean_for_llm(result.output)
                        obs = ObservationEvent(
                            action_id=action.id,
                            tool=tc["name"],
                            output=cleaned_output,
                            is_error=result.is_error,
                            metadata=result.metadata,
                        )
                        self.append(obs)
                        yield obs
                    continue
                else:
                    cleaned_content = strip_ansi(collected_content or "")
                    msg = MessageEvent(role="assistant", content=cleaned_content)
                    self.append(msg)
                    yield msg
                    finish = FinishEvent(reason="completed")
                    self.append(finish)
                    yield finish
                    await end_task_notification(cleaned_content[:80] if cleaned_content else "Done")
                    return

            except Exception as e:
                err = AgentErrorEvent(message=f"Stream error: {type(e).__name__}: {e}")
                self.append(err)
                yield err
                await end_task_notification("Error")
                return

        err = AgentErrorEvent(
            message=f"Reached max tool calls ({self.config.max_iterations}). "
                    f"Summary:\n{self._task_summary}"
        )
        self.append(err)
        yield err
        finish = FinishEvent(reason="max_iterations")
        self.append(finish)
        yield finish
        await end_task_notification("Max calls reached")

    # --- Approval flow ---
    async def request_approval(self, action_id: str, prompt: str) -> bool:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._approval_queue[action_id] = fut
        try:
            decision = await asyncio.wait_for(fut, timeout=300)
            return decision == "approved"
        except asyncio.TimeoutError:
            return False
        finally:
            self._approval_queue.pop(action_id, None)

    def resolve_approval(self, action_id: str, decision: str, reason: str = "") -> None:
        fut = self._approval_queue.get(action_id)
        if fut and not fut.done():
            fut.set_result(decision)


def _truncate_args(args: dict, max_len: int = 60) -> str:
    """Truncate tool args for summary display."""
    parts = []
    for k, v in args.items():
        vs = str(v)
        if len(vs) > 30:
            vs = vs[:27] + "..."
        parts.append(f"{k}={vs}")
    s = ", ".join(parts)
    return s[:max_len] + "..." if len(s) > max_len else s
