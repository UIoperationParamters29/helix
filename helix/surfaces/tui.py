"""HELIX TUI — full-screen interactive terminal UI.

Inspired by Hermes Agent's TUI:
  - Alternate-screen rendering (full-screen, no scrollback clutter)
  - Multi-pane layout: header / chat / sidebar / input
  - Live streaming: events appear as they happen
  - Sidebar with skills, memory, recent tools
  - Slash commands: /help /skills /memory /tools /new /exit
  - Non-blocking: queue messages while agent works
  - Status bar: provider/model/tools/iteration

Run with: helix tui
"""
from __future__ import annotations

import asyncio, sys, time
from typing import Optional

from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.table import Table
from rich.align import Align
from rich import box
from rich.spinner import Spinner

from ..config import HelixConfig
from ..conversation import Conversation
from ..events import (
    Event, MessageEvent, ActionEvent, ObservationEvent,
    AgentErrorEvent, FinishEvent, CondensationEvent,
)
from ..tools import all_tools
from ..skills.loader import load_skill_summaries
from ..memory.manager import load_memory
from .cli import _format_tool_args


class TUIState:
    """Mutable state rendered by the TUI."""

    def __init__(self, config: HelixConfig):
        self.config = config
        self.chat_lines: list[RenderableType] = []
        self.status: str = "ready"
        self.is_working: bool = False
        self.iteration: int = 0
        self.max_iter: int = config.max_iterations
        self.tool_counts: dict[str, int] = {}
        self.last_error: str | None = None
        self.message_count: int = 0
        self.session_id: str = ""
        self.spinner_frame: int = 0
        # Streaming state
        self._streaming_active: bool = False
        self._streaming_index: int | None = None
        self._streaming_content: str = ""

    def add_event(self, event: Event) -> None:
        if isinstance(event, MessageEvent):
            if event.role == "user":
                self.chat_lines.append(Text.assemble(
                    ("You", "bold cyan"),
                    (": ", "dim"),
                    (event.content, "white"),
                ))
                self.message_count += 1
            elif event.role == "assistant":
                # Streaming: if last line is a partial assistant message, update it.
                # Otherwise, add a new "HELIX:" header + content.
                # We detect partial by checking if the last entry is a Text starting with "HELIX:"
                # OR a Markdown (already-rendered assistant content).
                # For streaming, we track via _streaming_index.
                if self._streaming_active and self._streaming_index is not None:
                    # Update the streaming content in place
                    self._streaming_content = event.content
                else:
                    # New assistant message
                    self._streaming_active = True
                    self._streaming_content = event.content
                    self._streaming_index = len(self.chat_lines)
                    self.chat_lines.append(Text.assemble(
                        ("HELIX", "bold blue"),
                        (": ", "dim"),
                        (event.content, "white"),
                    ))
                    self.message_count += 1
        elif isinstance(event, ActionEvent):
            # Finalize any streaming text
            self._finalize_streaming()
            args_str = _format_tool_args(event.tool, event.args)
            self.chat_lines.append(Text.assemble(
                ("  ↳ ", "dim"),
                (event.tool, "bold yellow"),
                (f"({args_str})", "yellow"),
            ))
            self.tool_counts[event.tool] = self.tool_counts.get(event.tool, 0) + 1
        elif isinstance(event, ObservationEvent):
            self._finalize_streaming()
            icon = "✗" if event.is_error else "✓"
            color = "red" if event.is_error else "green"
            output = event.output.strip()
            if len(output) > 300:
                output = output[:150] + f" …(+{len(output)-300} chars)" + output[-150:]
            lines = output.splitlines()
            if len(lines) > 4:
                output = "\n".join(lines[:3]) + f"\n  …(+{len(lines)-3} more lines)"
            for line in output.splitlines():
                self.chat_lines.append(Text(f"      {icon} {line}", style=color))
        elif isinstance(event, AgentErrorEvent):
            self._finalize_streaming()
            self.chat_lines.append(Text.assemble(
                ("  ✗ ", "bold red"),
                (event.message[:300], "red"),
            ))
            self.last_error = event.message
        elif isinstance(event, FinishEvent):
            self._finalize_streaming()
            if event.reason == "completed":
                self.status = "ready"
            else:
                self.status = f"done ({event.reason})"

    def _finalize_streaming(self) -> None:
        """Convert the streaming placeholder into a final rendered message."""
        if not self._streaming_active or self._streaming_index is None:
            return
        content = self._streaming_content or ""
        idx = self._streaming_index
        # Replace the placeholder with a properly rendered version
        if idx < len(self.chat_lines):
            try:
                self.chat_lines[idx] = Group(
                    Text.assemble(("HELIX", "bold blue"), (":", "dim")),
                    Markdown(content) if content.strip() else Text("(empty response)", "dim"),
                )
            except Exception:
                self.chat_lines[idx] = Text.assemble(
                    ("HELIX", "bold blue"),
                    (": ", "dim"),
                    (content, "white"),
                )
        self._streaming_active = False
        self._streaming_index = None
        self._streaming_content = ""

    def update_streaming_display(self) -> None:
        """Refresh the streaming placeholder with current content (called during render)."""
        if not self._streaming_active or self._streaming_index is None:
            return
        idx = self._streaming_index
        content = self._streaming_content or ""
        if idx < len(self.chat_lines):
            self.chat_lines[idx] = Text.assemble(
                ("HELIX", "bold blue"),
                (": ", "dim"),
                (content, "white"),
                ("▌", "blue"),  # streaming cursor
            )


def _build_layout() -> Layout:
    """Build the full-screen layout."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=2),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=2),
    )
    layout["body"].split_row(
        Layout(name="chat", ratio=3),
        Layout(name="sidebar", ratio=2),
    )
    return layout


def _render_header(state: TUIState) -> RenderableType:
    """Top status bar."""
    cfg = state.config
    tools_n = len(all_tools(cfg))
    on_termux = "📱 Termux" if cfg.on_termux else "💻 PC"

    if state.is_working:
        status_icon = "●"
        status_color = "yellow"
        status_text = f"working (iter {state.iteration}/{state.max_iter})"
    elif state.last_error:
        status_icon = "●"
        status_color = "red"
        status_text = "error"
    else:
        status_icon = "●"
        status_color = "green"
        status_text = "ready"

    # Model display — shorten long names
    model_short = cfg.model
    if len(model_short) > 30:
        model_short = model_short[:27] + "..."

    line1 = Text.assemble(
        (" HELIX ", "bold white on blue"),
        (" v0.1.0 ", "dim"),
        (f" {status_icon} ", status_color),
        (status_text + "  ", status_color),
        (f"⚡ {cfg.provider}", "cyan"),
        ("/", "dim"),
        (model_short, "cyan"),
        ("  "),
        (f"🔧 {tools_n} tools", "dim"),
        ("  "),
        (f"{on_termux}", "magenta"),
    )

    line2 = Text.assemble(
        (f" session: {state.session_id[:16] if state.session_id else 'none'}", "dim"),
        ("  "),
        (f"messages: {state.message_count}", "dim"),
        ("  "),
        (f"tool calls: {sum(state.tool_counts.values())}", "dim"),
    )

    return Group(line1, line2)


def _render_chat(state: TUIState) -> RenderableType:
    """Main chat area."""
    # Update streaming display before rendering
    state.update_streaming_display()
    lines = state.chat_lines[-100:]  # last 100 renderables

    if not lines:
        content = Align.center(
            Group(
                Text(""),
                Text("🧬 HELIX is ready", style="bold blue", justify="center"),
                Text(""),
                Text("Type a message below to start.", style="dim", justify="center"),
                Text("Slash commands: /help /skills /memory /tools /new /exit", style="dim", justify="center"),
                Text(""),
                Text("Try: 'take a screenshot' or 'what's my battery level?'", style="dim italic", justify="center"),
            ),
            vertical="middle",
        )
    else:
        elements = list(lines)
        # Add streaming indicator at the bottom if working
        if state.is_working:
            spinner_text = Text.assemble(
                ("  ", "dim"),
                Spinner("dots", text=Text(" HELIX is thinking...", style="dim")),
            )
            elements.append(spinner_text)
        content = Group(*elements)

    return Panel(
        content,
        title="[bold blue]Chat[/]",
        border_style="blue",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _render_sidebar(state: TUIState) -> RenderableType:
    """Right sidebar: skills + memory + recent tools."""
    elements: list[RenderableType] = []

    # --- Skills ---
    skills = load_skill_summaries(state.config.home)
    skills_text = Text()
    if skills:
        for s in skills[:8]:
            skills_text.append(f"• {s['name']}\n", "green")
            desc = s['description'][:60]
            skills_text.append(f"  {desc}\n\n", "dim")
        if len(skills) > 8:
            skills_text.append(f"  +{len(skills) - 8} more\n", "dim")
    else:
        skills_text = Text("(no skills yet — agent creates them after tasks)", "dim italic")
    elements.append(Panel(
        skills_text,
        title=f"[bold green]Skills ({len(skills)})[/]",
        border_style="green",
        box=box.ROUNDED,
        padding=(0, 1),
    ))

    # --- Memory ---
    mem = load_memory(state.config.home)
    mem_text = Text()
    for kind in ("USER", "MEMORY"):
        if kind in mem:
            # First 2 non-empty lines
            mem_lines = [l for l in mem[kind].splitlines() if l.strip()][:2]
            summary = " | ".join(mem_lines)
            if len(summary) > 80:
                summary = summary[:77] + "..."
            mem_text.append(f"{kind}: ", "magenta")
            mem_text.append(f"{summary}\n", "dim")
    if not mem_text:
        mem_text = Text("(empty — agent fills via memory_update)", "dim italic")
    elements.append(Panel(
        mem_text,
        title="[bold magenta]Memory[/]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(0, 1),
    ))

    # --- Recent tools ---
    if state.tool_counts:
        tools_table = Table(show_header=False, box=None, padding=0, expand=True)
        tools_table.add_column("tool", style="yellow", ratio=3)
        tools_table.add_column("count", style="dim", justify="right", ratio=1)
        for tool, count in sorted(state.tool_counts.items(), key=lambda x: -x[1])[:10]:
            # Shorten tool name
            short = tool.replace("phone_", "ph_").replace("file_", "f_")
            tools_table.add_row(short, str(count))
        tools_content = tools_table
    else:
        tools_content = Text("(no tool calls yet)", "dim italic")
    elements.append(Panel(
        tools_content,
        title=f"[bold yellow]Tools used ({sum(state.tool_counts.values())})[/]",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    ))

    return Group(*elements)


def _render_footer(state: TUIState) -> RenderableType:
    """Bottom input hint bar."""
    if state.is_working:
        return Text.assemble(
            ("  ", "dim"),
            ("● ", "yellow"),
            ("HELIX is working — type to queue, Enter to send when ready", "dim"),
        )
    return Text.assemble(
        ("  ", "dim"),
        ("› ", "bold cyan"),
        ("type your message — Enter to send, /help for commands", "dim"),
    )


def _refresh(layout: Layout, state: TUIState) -> None:
    """Update all panes."""
    layout["header"].update(_render_header(state))
    layout["chat"].update(_render_chat(state))
    layout["sidebar"].update(_render_sidebar(state))
    layout["footer"].update(_render_footer(state))


async def tui_main(config: HelixConfig) -> None:
    """Run the TUI main loop."""
    state = TUIState(config)
    conv = Conversation(config=config)
    state.session_id = conv.session_id

    layout = _build_layout()
    _refresh(layout, state)

    # Message queue for non-blocking input
    message_queue: asyncio.Queue[str] = asyncio.Queue()

    async def input_loop():
        """Read input from the user (non-blocking via asyncio)."""
        loop = asyncio.get_event_loop()
        while True:
            # Use run_in_executor to avoid blocking
            try:
                user_input = await loop.run_in_executor(None, _read_input, state)
            except (EOFError, KeyboardInterrupt):
                print("\n[exit]")
                return
            if user_input is None:
                return
            await message_queue.put(user_input)

    async def agent_loop():
        """Process messages from the queue."""
        while True:
            user_input = await message_queue.get()
            if user_input is None:
                return

            # Slash commands
            if user_input.startswith("/"):
                cmd = user_input[1:].strip().lower()
                _handle_slash_command(cmd, state, conv, config)
                continue

            # Send to agent
            state.is_working = True
            state.status = "thinking"
            state.iteration = 0
            _refresh(layout, state)

            try:
                async for event in conv.send_streaming(user_input):
                    state.add_event(event)
                    if isinstance(event, ActionEvent):
                        state.iteration += 1
                    _refresh(layout, state)
            except Exception as e:
                state.chat_lines.append(Text(f"  ✗ Fatal error: {e}", "bold red"))
                state.last_error = str(e)

            state.is_working = False
            state.status = "ready"
            state.iteration = 0
            _refresh(layout, state)

    # Run input + agent loops concurrently with Live display
    input_task = asyncio.create_task(input_loop())
    agent_task = asyncio.create_task(agent_loop())

    try:
        with Live(
            layout,
            screen=True,           # alternate screen — no scrollback clutter
            refresh_per_second=10,  # smooth
            transient=False,        # keep the display on exit
            redirect_stdout=False,
            redirect_stderr=False,
        ) as live:
            # Periodic refresh for spinner animation
            while not input_task.done() and not agent_task.done():
                state.spinner_frame += 1
                _refresh(layout, state)
                await asyncio.sleep(0.1)

            # Wait for both to finish
            await asyncio.gather(input_task, agent_task, return_exceptions=True)
    except KeyboardInterrupt:
        pass
    finally:
        # Clear alternate screen and print final message
        print("\n[HELIX TUI exited]")


def _read_input(state: TUIState) -> Optional[str]:
    """Read input from stdin (blocking — called in executor)."""
    try:
        # Use a simple input() — the Live display is on the alternate screen
        # so input won't mess up the display.
        # We temporarily pause the live display for input.
        return input("› ")
    except (EOFError, KeyboardInterrupt):
        return None


def _handle_slash_command(cmd: str, state: TUIState, conv: Conversation, config: HelixConfig) -> None:
    """Handle slash commands — adds output to chat_lines."""
    parts = cmd.split(maxsplit=1)
    command = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("exit", "quit"):
        state.chat_lines.append(Text("  Use Ctrl+C to exit.", "dim"))
    elif command == "help":
        state.chat_lines.append(Text("  Commands:", "bold"))
        for c, desc in [
            ("/help", "show this help"),
            ("/skills", "list all skills"),
            ("/memory", "show memory files"),
            ("/tools", "list all tools"),
            ("/new", "start a new session"),
            ("/exit", "exit (or Ctrl+C)"),
        ]:
            state.chat_lines.append(Text(f"    {c:12} {desc}", "dim"))
    elif command == "skills":
        skills = load_skill_summaries(config.home)
        if not skills:
            state.chat_lines.append(Text("  (no skills yet)", "dim"))
        for s in skills:
            state.chat_lines.append(Text.assemble(
                (f"  {s['name']}", "bold green"),
                (f" — {s['description']}", "dim"),
            ))
    elif command == "memory":
        mem = load_memory(config.home)
        for kind in ("IDENTITY", "USER", "MEMORY"):
            if kind in mem:
                state.chat_lines.append(Text(f"  [{kind}]", "bold magenta"))
                for line in mem[kind].splitlines()[:5]:
                    state.chat_lines.append(Text(f"    {line}", "dim"))
    elif command == "tools":
        tools = all_tools(config)
        for t in tools:
            danger = " ⚠" if t.dangerous else ""
            state.chat_lines.append(Text.assemble(
                (f"  {t.name}", "bold yellow"),
                (danger, "red"),
                (f" — {t.description[:60]}", "dim"),
            ))
    elif command == "new":
        # Create a new conversation — note: this doesn't fully work in TUI
        # because we need to restart the agent loop. Just inform the user.
        state.chat_lines.append(Text("  Start a new session by exiting (Ctrl+C) and running 'helix tui' again.", "dim"))
    else:
        state.chat_lines.append(Text(f"  Unknown command: /{command} (try /help)", "red"))
