# HELIX

**Self-improving agent harness. Phone-native. Red & blue DNA.**

HELIX is an open-source agent harness that runs on your PC **and** inside Termux on Android, giving an LLM real tools to accomplish real tasks — shell, file ops, web, and (on phone) full device control including UI automation via self-ADB.

It synthesizes the best ideas from production agent harnesses:

| Stolen from | What we take |
|---|---|
| **Hermes** (Nous Research) | 6 core principles — prompt stability, progressive disclosure, self-registration, profile isolation, agent-owned learning |
| **OpenHands** (formerly OpenDevin) | Event-sourced architecture — append-only EventLog as single source of truth, stateless Agent, swappable Workspace |
| **OpenClaw** | Plugin SDK barrels, harness registry, tool policy + before/after hooks |
| **SWE-agent** | Deliberate Agent-Computer Interface (ACI) design |
| **Cline / MCP** | Model Context Protocol integration (pluggable external tool servers) |
| **Termux + self-ADB** | Phone control without root — `termux-api` for hardware, self-ADB for UI automation |

---

## What you get

- **42 tools** out of the box: bash, file ops, web fetch/search, skill management, memory, **plus 25+ phone tools**
- **Self-improving**: agent writes skills (`skill_manage`) and memory notes after solving tasks — gets smarter over time
- **Event-sourced**: every interaction is a typed event in an append-only log; replayable, debuggable
- **Multi-provider LLM**: OpenAI, Anthropic, Z.ai (GLM), Ollama, LM Studio — any OpenAI-compatible endpoint
- **Phone control** (Termux + ADB): SMS, calls, camera, GPS, sensors, torch, notifications, TTS, **UI automation** (tap, swipe, type, screenshot, dump UI tree, launch apps)
- **PWA web UI**: red & blue DNA theme, mobile-first, installable on phone home screen
- **Profile isolation**: multiple agents coexist via `HELIX_HOME` env var
- **Security**: risk analyzer + approval policy; dangerous commands blocked by default

---

## Quick start

### On PC (Linux/macOS/WSL)

```bash
git clone https://github.com/UIoperationParamters29/helix.git
cd helix
bash scripts/install_pc.sh

# Set your LLM key
export OPENAI_API_KEY=sk-...

# Start the web UI
helix web
# → open http://localhost:8765

# Or chat in terminal
helix chat
```

### On Android (Termux)

1. Install [Termux from F-Droid](https://f-droid.org/packages/com.termux/) (NOT Play Store — that version is deprecated)
2. Install [Termux:API from F-Droid](https://f-droid.org/packages/com.termux.api/)
3. In Termux:
   ```bash
   pkg install -y curl git python nodejs
   git clone https://github.com/UIoperationParamters29/helix.git
   cd helix
   bash scripts/install_termux.sh
   ```
4. Pair self-ADB for UI control (recommended):
   ```bash
   bash scripts/setup_adb.sh
   ```
5. Set your LLM key + start:
   ```bash
   export OPENAI_API_KEY=sk-...
   helix web
   ```
6. In any browser: `http://localhost:8765` — or "Add to Home Screen" for a native-feeling PWA.

---

## Using Z.ai GLM as the LLM

```bash
export HELIX_PROVIDER=zai
export ZAI_API_KEY=your_zai_key
helix web
```

## Using local Ollama (no API key needed)

```bash
# Install Ollama: https://ollama.com
ollama pull qwen2.5:7b
ollama serve  # starts on port 11434

export HELIX_PROVIDER=ollama
export HELIX_BASE_URL=http://localhost:11434/v1
export HELIX_MODEL=qwen2.5:7b
export HELIX_API_KEY=ollama  # any non-empty string
helix web
```

---

## Architecture in 30 seconds

```
┌─────────────────────────────────────────────────────────────┐
│ SURFACES (CLI / Web PWA / future: Telegram)                │
└──────────────────────┬──────────────────────────────────────┘
                       │  (events stream via WebSocket)
┌──────────────────────▼──────────────────────────────────────┐
│ Conversation  (the only mutable thing; owns EventLog)      │
│   └─ Agent loop: build prompt → LLM → tool calls → obs → …│
└──┬───────────┬───────────┬──────────────┬──────────────────┘
   │           │           │              │
   ▼           ▼           ▼              ▼
┌──────┐  ┌────────┐  ┌─────────┐  ┌──────────────┐
│ LLM  │  │ Tools  │  │ Skills  │  │   Memory     │
│ (any)│  │ (42)   │  │ (L0/L1) │  │ IDENTITY/USER│
└──────┘  └────┬───┘  └─────────┘  │ /MEMORY.md   │
               │                   └──────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Workspace: Local | Termux | Docker (stub) | Remote (stub)  │
│   Phone tools: termux-api + adb shell (self-paired)        │
└─────────────────────────────────────────────────────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

---

## Self-improvement loop

After solving a non-trivial task, the agent is encouraged to:

1. **Append a lesson to `MEMORY.md`** via `memory_update`
2. **Create a reusable skill** via `skill_manage` if the procedure is generalizable

Future sessions discover skills via Level-0 summaries in the system prompt and pull full content on demand. This is the closed learning loop that makes HELIX grow more capable the longer it runs.

---

## Security model

- **Risk analyzer** scores every tool call: low / medium / high / critical
- **Approval policy** auto-approves reads; requires approval for writes/destructive ops (configurable)
- **Dangerous patterns** regex-blocked by default (`rm -rf /`, fork bombs, `dd of=/dev/`, etc.)
- **Profile isolation** via `HELIX_HOME` — multiple agents don't share state
- **No telemetry.** HELIX runs entirely on your device. LLM calls go directly to your configured provider.

See [`docs/SECURITY.md`](docs/SECURITY.md) for details.

---

## Project structure

```
helix/
├── helix/                    # Python package
│   ├── agent / conversation / events    # Core runtime (event-sourced)
│   ├── llm/                  # Provider abstraction (OpenAI, Anthropic, Z.ai, Ollama)
│   ├── tools/                # 42 tools: bash, file, web, skills, memory, phone/*
│   │   └── phone/            # Termux:API + self-ADB UI control
│   ├── workspaces/           # Local | Termux | Docker (stub)
│   ├── skills/ memory/ security/        # Subsystems
│   └── surfaces/             # CLI + FastAPI/WebSocket server
├── web/                      # Next.js 14 PWA (red & blue theme)
│   ├── app/ components/ lib/
│   └── public/               # manifest.json + icons (installable)
├── scripts/                  # install_termux.sh, install_pc.sh, setup_adb.sh
└── docs/                     # ARCHITECTURE, PHONE_SETUP, SECURITY, SKILL_DEV
```

---

## Roadmap

- [x] Core agent runtime (event-sourced, multi-provider LLM)
- [x] 42 tools (filesystem, web, skills, memory, phone)
- [x] Phone UI automation via self-ADB
- [x] PWA web UI (red & blue, mobile-first, installable)
- [x] Self-improvement loop (skills + memory)
- [ ] MCP server integration (plug any MCP server as a tool source)
- [ ] Sub-agent delegation (parallel agents on shared workspace)
- [ ] Stuck detection (identical observations → escape hatch)
- [ ] Condenser (auto-summarize old events when context grows)
- [ ] Telegram gateway (chat with HELIX from anywhere)
- [ ] Shizuku integration (no wireless ADB dance)
- [ ] Android accessibility service APK (richer UI automation, no ADB)

---

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

HELIX stands on the shoulders of giants. The architecture is a deliberate synthesis of ideas from:
- [OpenHands](https://github.com/OpenHands/openhands) — event-sourced design, stateless agent
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — skills system, progressive disclosure, self-improvement loop
- [OpenClaw](https://docs.openclaw.ai/) — plugin SDK, harness registry, tool policy
- [SWE-agent](https://github.com/swe-agent/swe-agent) — Agent-Computer Interface design
- [Termux](https://termux.dev/) + [Termux:API](https://wiki.termux.com/wiki/Termux:API) — Linux on Android
- [Shizuku](https://shizuku.rikka.app/) — ADB-level permissions without root

Read the deep-dive guides that informed this design:
- [OpenHands Deep Dive & Build-Your-Own Guide](https://dev.to/truongpx396/openhands-deep-dive-build-your-own-guide-1al0)
- [Hermes Agent Deep Dive & Build-Your-Own Guide](https://dev.to/truongpx396/hermes-agent-deep-dive-build-your-own-guide-1pcc)
- [Learn Harness Engineering by Building a Mini OpenClaw](https://dev.to/truongpx396/learn-harness-engineering-by-building-a-mini-openclaw-bdm)
