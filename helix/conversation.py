"""Conversation — owns state, drives the loop, persists the EventLog.

This is the only mutable thing in the system (OpenHands V1 principle).
The Agent itself is a pure function: history -> next Action.
"""
from __future__ import annotations

import asyncio, json, time, uuid
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

    # --- Event log ---
    def append(self, event: Event) -> None:
        """Append an event + notify listeners + persist."""
        self.events.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass
        # Persist (append-only JSONL)
        try:
            with open(self._session_file, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except Exception:
            pass

    def add_listener(self, fn: Callable[[Event], None]) -> None:
        self._listeners.append(fn)

    def load_history(self) -> None:
        """Replay session file into self.events."""
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

    # --- System prompt assembly ---
    def _build_system_prompt(self) -> str:
        """Assemble the system prompt. Stable within a session (cache-friendly).

        Layers:
          1. Identity (who the agent is)
          2. User facts (from USER.md)
          3. Memory (from MEMORY.md)
          4. Skill summaries (Level 0 — names + descriptions)
          5. Tool usage instructions
          6. Platform context (Termux / PC, ADB status, etc.)
          7. Behavioral rules
        """
        mem = load_memory_for_prompt(self.config.home)
        skills = load_skill_summaries_for_prompt(self.config.home) if self.config.skills_enabled else []

        identity = mem.get("IDENTITY") or self._default_identity()
        user_facts = mem.get("USER", "")
        memory = mem.get("MEMORY", "")

        skills_block = ""
        if skills:
            skills_block = "\n\n## Available skills (Level 0)\n"
            skills_block += "Call `skill_read` to load full content of any skill before applying it.\n\n"
            for s in skills:
                skills_block += f"- **{s['name']}**: {s['description']}\n"

        platform = self._platform_context()

        return f"""# {self.config.persona}

{identity}

## About the user
{user_facts or "(no user facts recorded yet — learn them via conversation)"}

## Persistent memory
{memory or "(no persistent notes yet)"}
{skills_block}

## Capabilities
You are running on {platform}.
You have access to tools: bash, file_read/write/edit/list/search, web_fetch, web_search,
skill_list/read/manage, memory_read/update.
{self._phone_tools_block()}

## Behavioral rules
1. **Plan first, act second.** For non-trivial tasks, lay out 2-5 steps before calling tools.
2. **Verify before claiming.** After an action, check the observation. Don't assume success.
3. **Be concise.** No filler. No "I'll now...". Just do it.
4. **Learn from mistakes.** If something fails twice, try a different approach.
5. **Persist lessons.** After solving a non-trivial problem, append the lesson to MEMORY via memory_update.
   If the procedure is reusable, create a skill via skill_manage.
6. **Respect limits.** Don't run destructive commands without warning the user.
7. **Phone safety.** Sending SMS, making calls, posting notifications — confirm with the user first
   unless they explicitly authorized it.

## Tool use
Call tools via function calls. Read tool output carefully before next action.
If a tool returns an error, read the error and adapt — don't repeat the same call.
"""

    def _default_identity(self) -> str:
        return (
            "You are HELIX, a self-improving agent that runs on the user's own devices. "
            "You can execute shell commands, edit files, browse the web, and on phones: "
            "send SMS, take photos, control the UI via ADB, and more. "
            "You write your own skills and memory files to grow more capable over time."
        )

    def _phone_tools_block(self) -> str:
        if self.config.on_termux:
            return (
                "\n## Phone control (Termux + ADB)\n"
                "You are running inside Termux on Android. You can:\n"
                "- Hardware: phone_battery, phone_sensor, phone_torch, phone_vibrate, phone_volume, phone_brightness\n"
                "- Communications: phone_sms_send, phone_sms_read, phone_call\n"
                "- System: phone_notification, phone_clipboard_get/set, phone_tts\n"
                "- Camera: phone_camera_photo\n"
                "- Location: phone_location\n"
                "- UI (requires self-ADB paired): phone_ui_tap, phone_ui_swipe, phone_ui_type, phone_ui_key, "
                "phone_ui_screenshot, phone_ui_dump, phone_screen_state, phone_screen_wake\n"
                "- Apps: phone_app_launch, phone_app_list, phone_app_current, phone_app_stop\n"
                "If a phone_ui_* tool fails with 'requires ADB', guide the user through pairing."
            )
        return (
            "\n## Phone control\n"
            "Not running on Termux. Phone tools will return errors if called. "
            "If the user wants phone control, point them to docs/PHONE_SETUP.md."
        )

    def _platform_context(self) -> str:
        import platform as plat
        if self.config.on_termux:
            return f"Termux on Android (aarch64). HELIX_HOME={self.config.home}"
        return f"{plat.system()} {plat.machine()}. HELIX_HOME={self.config.home}"

    # --- Main loop ---
    async def send(self, user_text: str) -> AsyncIterator[Event]:
        """Send a user message and stream the agent's response.

        Yields events as they happen. Caller can listen + render.
        """
        # Append user message
        user_evt = MessageEvent(role="user", content=user_text)
        self.append(user_evt)
        yield user_evt

        # Build the message history for the LLM (last N events as messages)
        messages = self._events_to_messages()
        system = self._build_system_prompt()

        # Agent loop: max_iterations rounds
        for iteration in range(self.config.max_iterations):
            # Call LLM
            try:
                resp = await self.llm.complete(messages=messages, tools=self._tool_schemas, system=system)
            except Exception as e:
                err = AgentErrorEvent(message=str(e))
                self.append(err)
                yield err
                return

            # If assistant wants to call tools
            if resp.tool_calls:
                # If there's also content (chain-of-thought), emit it as a message
                if resp.content:
                    thought = MessageEvent(role="assistant", content=resp.content)
                    self.append(thought)
                    yield thought
                    messages.append({"role": "assistant", "content": resp.content})

                # Dispatch each tool call
                for tc in resp.tool_calls:
                    action = ActionEvent(
                        tool=tc["name"],
                        args=tc.get("args", {}),
                        thought=resp.content or "",
                    )
                    # Replace action id with LLM's tool_call_id if present
                    action.id = tc.get("id", action.id)
                    self.append(action)
                    yield action
                    messages.append(action.to_message())

                    # Execute
                    result = await self.executor.execute(tc["name"], tc.get("args", {}))
                    obs = ObservationEvent(
                        action_id=action.id,
                        tool=tc["name"],
                        output=result.output,
                        is_error=result.is_error,
                        metadata=result.metadata,
                    )
                    self.append(obs)
                    yield obs
                    messages.append(obs.to_message())

                # Continue loop: model will see observations and decide next action
                continue
            else:
                # No tool calls — assistant is done
                msg = MessageEvent(role="assistant", content=resp.content or "")
                self.append(msg)
                yield msg
                finish = FinishEvent(reason="completed")
                self.append(finish)
                yield finish
                return

        # Hit iteration cap
        err = AgentErrorEvent(message=f"Hit max_iterations={self.config.max_iterations} without finishing")
        self.append(err)
        yield err
        finish = FinishEvent(reason="max_iterations")
        self.append(finish)
        yield finish

    def _events_to_messages(self) -> list[dict]:
        """Convert event log to LLM message format. Skips system + condensation events."""
        msgs = []
        # Simple condensation: if too many events, summarize older ones
        # (For v1 we just truncate to last 50 events to keep context manageable)
        events = self.events[-50:] if len(self.events) > 50 else self.events
        for e in events:
            if isinstance(e, (CondensationEvent, ApprovalEvent, FinishEvent)):
                continue
            msgs.append(e.to_message())
        return msgs

    # --- Approval flow (for dangerous tools) ---
    async def request_approval(self, action_id: str, prompt: str) -> bool:
        """Pause and wait for human approval. UI calls resolve_approval()."""
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._approval_queue[action_id] = fut
        # In a real implementation, this would emit an ApprovalRequestEvent
        # and the UI would call resolve_approval when user clicks Approve/Deny
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
