# HELIX Architecture

## Design principles (stolen from the best)

These are the rules every decision in HELIX traces back to.

### 1. Event-sourced (from OpenHands)

Every interaction is a typed event in an append-only log. The `EventLog` is the single source of truth. Replay = deterministic reconstruction of the entire conversation.

```python
Event
├── MessageEvent     (user / assistant text)
├── ActionEvent      (agent decided to call a tool)
├── ObservationEvent (tool returned a result)
├── AgentErrorEvent  (LLM or loop error)
├── CondensationEvent (old events summarized)
├── ApprovalEvent    (human approved/denied)
└── FinishEvent      (turn complete)
```

**Why:** debuggable, replayable, parallelizable. Every prompt/response/tool call is inspectable.

### 2. Stateless Agent (from OpenHands V1)

The Agent is a pure function: `history → next Action`. The `Conversation` owns state. Tools, LLM, Condenser are immutable Pydantic models. Only `ConversationState` is mutable, and it changes only by appending events.

**Why:** no hidden state to corrupt, easy to swap components, trivially testable.

### 3. Prompt stability (from Hermes)

The system prompt is assembled once at session start and does not mutate mid-conversation. This isn't aesthetic — it's economic. LLM prompt caches require a stable prefix. Mid-conversation toolset changes invalidate the cache and 10× cost.

**Implementation:** skills load as Level-0 summaries (name + 1-line desc) at session start. The agent pulls full content via `skill_read` only when needed — but those are user/assistant messages, not system prompt mutations.

### 4. Progressive disclosure (from Hermes)

Don't load every skill's full content into the system prompt. Three levels:

- **Level 0**: title + 1-line description (always in system prompt) — ~50 bytes per skill
- **Level 1**: full skill content (pulled on demand via `skill_read`) — typically 1-5 KB
- **Level 2**: referenced files (pulled when the skill instructs)

This is how HELIX can ship 42 tools and dozens of skills while staying under context limits.

### 5. Self-registration (from Hermes)

Tools register themselves at import time via the `@tool` decorator. New tool = one new file. No central `__all__` list to maintain.

```python
# helix/tools/my_tool.py
from .base import Tool, ToolResult, tool

@tool
class MyTool(Tool):
    name = "my_tool"
    description = "..."
    parameters = {...}
    async def run(self, **kwargs) -> ToolResult:
        ...
```

That's it. The tool is now registered and available to the agent.

### 6. Profile isolation (from Hermes)

Multiple agents coexist by each owning a `HELIX_HOME` directory (default `~/.helix`, override via env var). Every filesystem path goes through `get_helix_home()` — never hard-coded.

```bash
# Run two independent agents:
HELIX_HOME=~/.helix-work helix web --port 8765
HELIX_HOME=~/.helix-personal helix web --port 8766
```

### 7. Agent owns its learning (from Hermes)

Skills are not added by humans editing source code. The agent writes them via `skill_manage` after solving non-trivial tasks. Memory is not curated by humans — the agent edits `MEMORY.md` and `USER.md` between turns. This is the closed learning loop.

### 8. Code is the universal action (from OpenHands)

Don't design 20 bespoke tools. Give the agent `bash` + `file_edit` + `web_fetch` + (on phone) `phone_ui_*`, then let it write code to compose them. The tools are primitives; the LLM is the composer.

### 9. Optional isolation, not mandatory sandboxing (from OpenHands)

The agent runs in-process by default. Swap `LocalWorkspace` → `DockerWorkspace` for isolation without changing agent code. Don't make sandboxing a build-time decision.

### 10. Deliberate ACI (from SWE-agent)

The Agent-Computer Interface — the design of the tools the agent uses — matters more than model choice. Invest in tool ergonomics: clear error messages, structured returns, sensible defaults.

---

## Component map

```
┌─────────────────────────────────────────────────────────────────────┐
│ SURFACES                                                            │
│   helix/surfaces/cli.py           — Rich terminal UI                │
│   helix/surfaces/web_api/server.py — FastAPI + WebSocket            │
│   web/                            — Next.js 14 PWA (red/blue theme) │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ CORE                                                                │
│   conversation.py   — owns state + EventLog, drives the loop        │
│   events.py         — typed events (Pydantic)                       │
│   config.py         — HELIX_HOME, provider config, env overrides    │
└──┬──────────┬──────────┬──────────────┬───────────────┬────────────┘
   │          │          │              │               │
   ▼          ▼          ▼              ▼               ▼
┌──────┐ ┌────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
│ LLM  │ │ Tools  │ │ Skills   │ │  Memory    │ │  Security    │
│      │ │ (42)   │ │ loader   │ │  manager   │ │  policy +    │
│ OAI  │ │        │ │ L0/L1/L2 │ │  IDENTITY/ │ │  risk        │
│ Anth │ │ bash   │ │          │ │  USER/     │ │  analyzer    │
│ Z.ai │ │ file*  │ │          │ │  MEMORY.md │ │              │
│ Oll  │ │ web*   │ │          │ │            │ │              │
│ LMS  │ │ skill* │ │          │ │            │ │              │
│      │ │ mem*   │ │          │ │            │ │              │
│      │ │ phone* │ │          │ │            │ │              │
└──────┘ └───┬────┘ └──────────┘ └────────────┘ └──────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│ WORKSPACES                                                          │
│   LocalWorkspace    — direct subprocess (PC)                        │
│   TermuxWorkspace   — Termux + termux-api + adb (Android)           │
│   DockerWorkspace   — (stub) sandboxed container                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The agent loop (canonical)

```python
async def send(self, user_text: str) -> AsyncIterator[Event]:
    # 1. Append user message to EventLog
    self.append(MessageEvent(role="user", content=user_text))

    # 2. Build messages from event history + assemble system prompt (stable)
    messages = self._events_to_messages()
    system = self._build_system_prompt()  # identity + user + memory + skills L0 + rules

    # 3. Loop: max_iterations rounds
    for iteration in range(self.config.max_iterations):
        # 3a. Call LLM
        resp = await self.llm.complete(messages, tools=self._tool_schemas, system=system)

        # 3b. If tool calls: dispatch each, append Action + Observation, continue
        if resp.tool_calls:
            for tc in resp.tool_calls:
                action = ActionEvent(tool=tc["name"], args=tc["args"])
                self.append(action)
                result = await self.executor.execute(tc["name"], tc["args"])
                obs = ObservationEvent(action_id=action.id, output=result.output,
                                        is_error=result.is_error)
                self.append(obs)
                messages.extend([action.to_message(), obs.to_message()])
            continue

        # 3c. No tool calls: assistant is done
        self.append(MessageEvent(role="assistant", content=resp.content))
        self.append(FinishEvent(reason="completed"))
        return
```

---

## Tool execution pipeline

```
Agent calls tool
    ↓
ToolExecutor.execute(name, args)
    ↓
1. Resolve tool instance (cached)
2. Check danger: tool.check_dangerous(args) + RiskAnalyzer.assess(name, args)
3. Run before_hooks (policy, logging, approval gate)
4. Call tool.run(**args) → ToolResult
5. Run after_hooks (audit, telemetry)
6. Return ToolResult
    ↓
Conversation wraps as ObservationEvent → appends to EventLog
```

---

## Phone control architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ HELIX agent running in Termux                                   │
│   tools/phone/_common.py — is_termux(), adb_available()         │
└──────────┬──────────────────────────────────┬───────────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────────────┐    ┌─────────────────────────────┐
│ Termux:API tools            │    │ ADB UI tools                │
│  (termux-api CLI)           │    │  (adb shell input ...)      │
│                             │    │                             │
│  phone_sms_send/read        │    │  phone_ui_tap(x,y)          │
│  phone_call                 │    │  phone_ui_swipe(...)        │
│  phone_notification_*       │    │  phone_ui_type("text")      │
│  phone_camera_photo         │    │  phone_ui_key(keycode)      │
│  phone_location             │    │  phone_ui_screenshot()      │
│  phone_clipboard_get/set    │    │  phone_ui_dump()  (XML)     │
│  phone_battery/sensor       │    │  phone_screen_wake()        │
│  phone_torch/vibrate        │    │  phone_app_launch/stop/list │
│  phone_volume/brightness    │    │                             │
│  phone_tts                  │    │  Requires:                  │
│                             │    │   pkg install android-tools │
│  Requires:                  │    │   + self-ADB pairing        │
│   pkg install termux-api    │    │     (Android 11+)           │
│   + Termux:API app          │    │   OR Shizuku (no dance)     │
└─────────────────────────────┘    └─────────────────────────────┘
        ↓                                    ↓
   Android hardware               Android UI / window manager
   (no root needed)               (no root needed)
```

### Self-ADB pairing (the magic trick)

Android 11+ supports wireless ADB debugging. Termux can connect to the phone it's running on:

```bash
pkg install android-tools
# In phone settings: enable Wireless debugging → "Pair device with pairing code"
adb pair 192.168.1.42:37123   # enter pairing code
adb connect 192.168.1.42:41234
```

Now `adb shell` commands run from Termux control the phone's UI. HELIX's `phone_ui_*` tools wrap these.

**Alternative: Shizuku** — gives ADB-level permissions without the wireless ADB dance. Survives reboots. See https://shizuku.rikka.app/

---

## Configuration

All config in `HELIX_HOME/config.yaml` + env overrides (`HELIX_*` prefix).

```yaml
provider: openai         # openai | anthropic | zai | ollama | lmstudio | custom
model: gpt-4o-mini
base_url: null           # override for OpenAI-compatible endpoints
max_tokens: 8096
max_iterations: 30
max_context_tokens: 100000
auto_approve_reads: true
auto_approve_writes: false
dangerous_patterns:
  - "rm\\s+-rf\\s+/(?!tmp)"
  - "dd\\s+.*of=/dev/"
  # ... (see config.py)
web_host: 0.0.0.0
web_port: 8765
persona: HELIX
skills_enabled: true
skill_auto_create: true
```

---

## What's intentionally NOT here (yet)

- **Sub-agent delegation** — planned. Multiple agents on shared workspace.
- **Stuck detection** — planned. Identical observations N times → escape hatch.
- **Condenser** — planned. Auto-summarize old events when context > N tokens.
- **Telegram gateway** — planned. Chat with HELIX from anywhere.
- **MCP server integration** — planned. Plug any MCP server as a tool source.
- **Docker workspace** — stubbed. For sandboxed execution on PC.
- **Android accessibility service APK** — planned. Richer UI automation without ADB.

These are tracked in the README roadmap. Contributions welcome.
