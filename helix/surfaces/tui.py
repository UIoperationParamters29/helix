"""HELIX TUI — interactive terminal interface.

Scrolling chat (not full-screen) with streaming text, slash commands,
and compact status. Ctrl+C exits cleanly.
"""
from __future__ import annotations

import asyncio
from rich.console import Console
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel

from ..config import HelixConfig
from ..conversation import Conversation
from ..events import (
    Event, MessageEvent, ActionEvent, ObservationEvent,
    AgentErrorEvent, FinishEvent,
)
from ..tools import all_tools
from ..skills.loader import load_skill_summaries
from ..memory.manager import load_memory

console = Console()


def _fmt_args(args: dict, max_len: int = 80) -> str:
    parts = []
    for k, v in args.items():
        vs = v if isinstance(v, str) and len(v) <= 50 else (repr(v) if not isinstance(v, str) else v[:47] + "...")
        if isinstance(vs, str) and len(vs) > 50:
            vs = vs[:47] + "..."
        parts.append(f"{k}={vs}")
    s = ", ".join(parts)
    return s[:max_len] + "..." if len(s) > max_len else s


def _render_assistant(content: str) -> None:
    """Render assistant message as markdown, indented."""
    # Strip any ANSI/Rich color codes that leaked from tool outputs
    from ..text_utils import strip_ansi
    content = strip_ansi(content)
    if not content.strip():
        console.print("  [dim](empty response)[/]")
        return
    console.print("  [bold blue]HELIX:[/]")
    try:
        from io import StringIO
        buf = StringIO()
        sub = Console(file=buf, force_terminal=True, color_system="auto")
        sub.print(Markdown(content))
        for line in buf.getvalue().splitlines():
            console.print(f"  {line}")
    except Exception:
        for line in content.splitlines():
            console.print(f"  [white]{line}[/]")


async def tui_main(config: HelixConfig) -> None:
    """Run the interactive TUI."""
    import signal, asyncio
    from ..memory.manager import init_memory_files
    init_memory_files(config.home, config.persona)

    # Install SIGINT handler so Ctrl+C works even during blocking input().
    # Without this, Ctrl+C only fires after Enter is pressed (because input()
    # blocks the event loop from processing signals).
    def _sigint_handler(signum, frame):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGINT, _sigint_handler)
    except (ValueError, OSError):
        pass  # not in main thread

    conv = Conversation(config=config)

    # Compact banner
    console.print()
    console.print("  [bold blue]HELIX[/] [dim]v0.1.0[/]")
    console.print(f"  [dim]Model:[/] [cyan]{config.model}[/]  [dim]URL:[/] {config.base_url or '(default)'}")
    console.print(f"  [dim]Key:[/] {'✓' if config.api_key else '[red]✗ NOT SET[/]'}  "
                  f"[dim]Tools:[/] {len(all_tools(config))}  "
                  f"[dim]Session:[/] {conv.session_id[:12]}")
    if config.on_termux:
        console.print("  [magenta]📱 Termux[/]")
    console.print("  [dim]Type /help for commands · Ctrl+C to quit[/]")
    console.print()

    if not config.api_key:
        console.print("  [bold red]⚠ No API key![/]  [cyan]export HELIX_API_KEY=your_key[/]\n")

    iter_count = 0

    while True:
        # Status + prompt
        try:
            console.print(f"  [dim]iter {iter_count}/{config.max_iterations} · session {conv.session_id[:8]}[/]")
            user_input = console.input("[bold cyan]›[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Bye.[/]")
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            parts = user_input[1:].split()
            cmd = parts[0].lower() if parts else ""
            arg = " ".join(parts[1:]) if len(parts) > 1 else ""
            if _handle_slash(cmd, arg, config, conv):
                return
            continue

        # Send to agent
        iter_count = 0
        streaming_text = ""
        streaming_active = False

        try:
            async for event in conv.send_streaming(user_input):
                if isinstance(event, MessageEvent):
                    if event.role == "user":
                        console.print(f"  [bold cyan]You:[/] {event.content}")
                    elif event.role == "assistant":
                        streaming_active = True
                        streaming_text = event.content
                elif isinstance(event, ActionEvent):
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    iter_count += 1
                    console.print(f"  [dim][{iter_count}][/dim] [bold yellow]↳ {event.tool}[/]([yellow]{_fmt_args(event.args)}[/])")
                elif isinstance(event, ObservationEvent):
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    icon = "✗" if event.is_error else "✓"
                    color = "red" if event.is_error else "green"
                    output = event.output.strip()
                    if len(output) > 400:
                        output = output[:200] + f"\n      …(+{len(output)-400} chars)" + output[-200:]
                    lines = output.splitlines()
                    if len(lines) > 5:
                        output = "\n".join(lines[:4]) + f"\n      …(+{len(lines)-4} more)"
                    for line in output.splitlines():
                        console.print(f"      [ {icon} ] {line}", style=color)
                elif isinstance(event, AgentErrorEvent):
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    console.print(f"  [bold red]✗[/] [red]{event.message[:400]}[/]")
                elif isinstance(event, FinishEvent):
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    if event.reason != "completed":
                        console.print(f"  [dim]finished: {event.reason}[/]")
        except KeyboardInterrupt:
            console.print("\n  [yellow]⚠ Interrupted.[/]")
            if streaming_active and streaming_text:
                _render_assistant(streaming_text)
        except Exception as e:
            if streaming_active and streaming_text:
                _render_assistant(streaming_text)
            console.print(f"  [bold red]✗ Fatal:[/] {type(e).__name__}: {e}")

        console.print()  # blank line between turns


def _handle_slash(cmd: str, arg: str, config: HelixConfig, conv: Conversation) -> bool:
    """Handle slash command. Returns True if should exit."""
    if cmd in ("exit", "quit"):
        return True
    elif cmd == "help":
        console.print("  [bold]Commands:[/]")
        console.print("    [cyan]/help[/]     this help")
        console.print("    [cyan]/skills[/]   list skills")
        console.print("    [cyan]/memory[/]   show memory")
        console.print("    [cyan]/tools[/]    list tools")
        console.print("    [cyan]/test[/]     test LLM connection")
        console.print("    [cyan]/models[/]   list gateway models")
        console.print("    [cyan]/status[/]   show config")
        console.print("    [cyan]/exit[/]     quit (or Ctrl+C)")
    elif cmd == "skills":
        skills = load_skill_summaries(config.home)
        if not skills:
            console.print("  [dim](no skills yet — agent creates them after tasks)[/]")
        for s in skills:
            console.print(f"  [green]{s['name']}[/]: {s['description']}")
    elif cmd == "memory":
        mem = load_memory(config.home)
        for kind in ("IDENTITY", "USER", "MEMORY"):
            if kind in mem:
                console.print(Panel(mem[kind], title=kind, border_style="magenta"))
    elif cmd == "tools":
        for t in all_tools(config):
            danger = " [red]⚠[/]" if t.dangerous else ""
            console.print(f"  [yellow]{t.name}[/]{danger} — {t.description[:70]}")
    elif cmd == "status":
        console.print(f"  [dim]Model:[/] [cyan]{config.model}[/]")
        console.print(f"  [dim]URL:[/] {config.base_url or '(default)'}")
        console.print(f"  [dim]Key:[/] {'✓' if config.api_key else '[red]✗[/]'}")
        console.print(f"  [dim]Tools:[/] {len(all_tools(config))}")
        console.print(f"  [dim]Session:[/] {conv.session_id}")
    elif cmd == "test":
        _run_test(config)
    elif cmd == "models":
        _run_list_models(config, arg)
    else:
        console.print(f"  [red]Unknown: /{cmd}[/] (try /help)")
    return False


def _run_test(config: HelixConfig) -> None:
    """Test LLM connection."""
    from ..llm import get_llm
    console.print(f"  [dim]Testing {config.model}...[/]")
    try:
        llm = get_llm(config)

        async def _do():
            return await llm.complete(
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                tools=None, system="Reply with OK.",
            )
        resp = asyncio.run(_do())
        if resp.finish_reason == "error":
            console.print(f"  [bold red]✗ Failed[/]")
            if isinstance(resp.raw, dict):
                console.print(f"  [red]{resp.raw.get('error', '')[:300]}[/]")
                if resp.raw.get("hint"):
                    console.print(f"  [blue]Hint:[/] {resp.raw['hint']}")
        else:
            console.print(f"  [bold green]✓ Works![/] Replied: [cyan]{resp.content}[/]")
    except Exception as e:
        console.print(f"  [bold red]✗[/] {type(e).__name__}: {e}")


def _run_list_models(config: HelixConfig, filter_str: str = "") -> None:
    """List models on gateway."""
    import httpx
    if not config.base_url:
        console.print("  [red]No base_url set.[/]")
        return
    url = config.base_url.rstrip("/") + "/models"
    console.print(f"  [dim]Fetching {url}...[/]")
    try:
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        r = httpx.get(url, headers=headers, timeout=15)
        if r.status_code >= 400:
            console.print(f"  [red]✗ HTTP {r.status_code}[/]")
            return
        data = r.json()
        models = []
        if isinstance(data, dict) and "data" in data:
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
        models.sort()
        if filter_str:
            models = [m for m in models if filter_str.lower() in m.lower()]
        console.print(f"  [green]✓ {len(models)} models[/]")
        for m in models[:30]:
            marker = " [green]← current[/]" if m == config.model else ""
            console.print(f"    [yellow]{m}[/]{marker}")
        if len(models) > 30:
            console.print(f"    [dim]...and {len(models) - 30} more[/]")
    except Exception as e:
        console.print(f"  [red]✗[/] {e}")
