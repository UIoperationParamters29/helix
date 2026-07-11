"""Event types — the single source of truth.

Every interaction in HELIX is an event. The EventLog is append-only.
Replaying it reconstructs the entire conversation deterministically.
This is stolen directly from OpenHands V1, because it is correct.

Event hierarchy:
    Event
    ├── MessageEvent (user or assistant text)
    ├── ActionEvent (agent decided to call a tool)
    ├── ObservationEvent (tool returned a result)
    ├── AgentErrorEvent (LLM or loop error)
    ├── CondensationEvent (old events summarized to free context)
    ├── ApprovalEvent (human approved/denied a tool call)
    └── FinishEvent (turn complete)
"""
from __future__ import annotations

import time, uuid
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field


def _ts() -> float:
    return time.time()


def _id() -> str:
    return uuid.uuid4().hex[:16]


class Event(BaseModel):
    """Base event. Every event has: id, timestamp, type."""
    id: str = Field(default_factory=_id)
    ts: float = Field(default_factory=_ts)
    type: str = "event"

    def to_message(self) -> dict:
        """Render this event as a chat message for the LLM."""
        return {"role": "system", "content": f"[{self.type}]"}


class MessageEvent(Event):
    """A text message from user or assistant."""
    type: Literal["message"] = "message"
    role: Literal["user", "assistant", "system"]
    content: str

    def to_message(self) -> dict:
        return {"role": self.role, "content": self.content}


class ActionEvent(Event):
    """The agent decided to call a tool."""
    type: Literal["action"] = "action"
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    thought: str = ""                   # model's reasoning, if any

    def to_message(self) -> dict:
        # OpenAI tool_call format
        return {
            "role": "assistant",
            "content": self.thought or None,
            "tool_calls": [{
                "id": self.id,
                "type": "function",
                "function": {
                    "name": self.tool,
                    "arguments": _json_dumps(self.args),
                },
            }],
        }


class ObservationEvent(Event):
    """A tool returned a result."""
    type: Literal["observation"] = "observation"
    action_id: str                      # links back to ActionEvent.id
    tool: str
    output: str
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_message(self) -> dict:
        return {
            "role": "tool",
            "tool_call_id": self.action_id,
            "content": self.output,
        }


class AgentErrorEvent(Event):
    """LLM call or loop error."""
    type: Literal["error"] = "error"
    message: str
    traceback: str = ""

    def to_message(self) -> dict:
        return {"role": "system", "content": f"Error: {self.message}"}


class CondensationEvent(Event):
    """Old events were summarized to free context."""
    type: Literal["condensation"] = "condensation"
    summary: str
    summarized_ids: list[str] = Field(default_factory=list)


class ApprovalEvent(Event):
    """Human approved or denied a tool call."""
    type: Literal["approval"] = "approval"
    action_id: str
    decision: Literal["approved", "denied"]
    reason: str = ""


class FinishEvent(Event):
    """Turn complete."""
    type: Literal["finish"] = "finish"
    reason: str = "completed"


EventType = Union[
    MessageEvent, ActionEvent, ObservationEvent, AgentErrorEvent,
    CondensationEvent, ApprovalEvent, FinishEvent,
]


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, default=str, ensure_ascii=False)


def event_from_dict(d: dict) -> EventType:
    """Reconstruct an event from a dict (for replay)."""
    t = d.get("type", "event")
    mapping = {
        "message": MessageEvent,
        "action": ActionEvent,
        "observation": ObservationEvent,
        "error": AgentErrorEvent,
        "condensation": CondensationEvent,
        "approval": ApprovalEvent,
        "finish": FinishEvent,
    }
    cls = mapping.get(t, Event)
    return cls(**d)  # type: ignore
