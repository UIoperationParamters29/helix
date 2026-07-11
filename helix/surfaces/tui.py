"""HELIX TUI — interactive terminal interface.

Design: NOT a full-screen alternate-screen app (those break input() in most terminals).
Instead: a scrolling chat with rich formatting, streaming text, slash commands,
and a status line before each prompt. Like Hermes's classic CLI, enhanced.

Features:
  - Streaming: assistant text appears token-by-token
  - Compact colored tool calls (↳ tool_name(args))
  - Status line before each prompt (model/iter/tools)
  - Slash commands: /help /skills /memory /tools /sessions /new /exit
  - Markdown rendering for assistant responses
  - Error surfacing (never silent empty responses)
"""
from __future__ import annotations

import asyncio, sys, os, shlex
from typing import Optional

from rich.console import Console
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.align import Align
from rich.console import Group

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


def _fmt_args(args: dict, max_len: int = 100) -> str:
    """Compact arg formatting."""
    parts = []
    for k, v in args.items():
        if isinstance(v, str):
            vs = v if len(v) <= 60 else v[:57] + "..."
        else:
            vs = repr(v)
            if len(vs) > 60:
                vs = vs[:57] + "..."
        parts.append(f"{k}={vs}")
    s = ", ".join(parts)
    return s[:max_len] + "..." if len(s) > max_len else s


def _status_line(config: HelixConfig, conv: Conversation, iter_count: int = 0) -> str:
    """One-line status shown before the input prompt."""
    tools_n = len(all_tools(config))
    on_phone = "📱" if config.on_termux else "💻"
    # Shorten model name
    model = config.model
    if len(model) > 25:
        model = model[:22] + "..."
    base = config.base_url or "(default)"
    # Show if key is set
    key_status = "🔑" if config.api_key else "⚠️nokey"
    return (f"[dim]{on_phone}[/] [cyan]{config.provider}[/]/[cyan]{model}[/] "
            f"[dim]🔧{tools_n}[/] [dim]iter {iter_count}/{config.max_iterations}[/] "
            f"[dim]{key_status}[/] [dim]session:{conv.session_id[:8]}[/]")


async def tui_main(config: HelixConfig) -> None:
    """Run the interactive TUI."""
    from ..memory.manager import init_memory_files
    init_memory_files(config.home, config.persona)

    conv = Conversation(config=config)

    # Banner
    console.print(Panel.fit(
        f"[bold blue]HELIX[/] [dim]v0.1.0[/]\n"
        f"[dim]Provider:[/] [cyan]{config.provider}[/]  [dim]Model:[/] [cyan]{config.model}[/]\n"
        f"[dim]Base URL:[/] {config.base_url or '(provider default)'}\n"
        f"[dim]API key:[/] {'✓ set' if config.api_key else '[red]✗ NOT SET[/]'}\n"
        f"[dim]Home:[/] {config.home}\n"
        f"[dim]Tools:[/] {len(all_tools(config))} registered  [dim]Termux:[/] {'yes' if config.on_termux else 'no'}\n"
        f"[dim]Type [bold]/help[/] for commands, [bold]/exit[/] to quit.[/]",
        border_style="blue",
    ))

    # Warn if no API key
    if not config.api_key:
        console.print("[bold red]⚠ No API key set![/]  Set it with:\n"
                      "  [cyan]export HELIX_API_KEY=your_key[/]\n"
                      "  [cyan]helix tui[/]\n")

    iter_count = 0

    while True:
        # Status line + prompt
        console.print(_status_line(config, conv, iter_count))
        try:
            user_input = console.input("[bold cyan]›[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/]")
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        # --- Slash commands ---
        if user_input.startswith("/"):
            cmd = user_input[1:].split()[0].lower() if user_input[1:].split() else ""
            arg = user_input[1:].split(maxsplit=1)[1] if len(user_input[1:].split(maxsplit=1)) > 1 else ""
            should_exit = _handle_slash(cmd, arg, config, conv)
            if should_exit:
                return
            continue

        # --- Send to agent with streaming ---
        iter_count = 0
        streaming_text = ""
        streaming_active = False

        try:
            async for event in conv.send_streaming(user_input):
                if isinstance(event, MessageEvent):
                    if event.role == "user":
                        console.print(Text.assemble(
                            ("You", "bold cyan"),
                            (": ", "dim"),
                            (event.content, "white"),
                        ))
                    elif event.role == "assistant":
                        if not streaming_active:
                            streaming_active = True
                            streaming_text = event.content
                        else:
                            streaming_text = event.content
                        # We'll render the final version on finish or before a tool call
                        # (rendering every token is too flickery in non-screen mode)
                elif isinstance(event, ActionEvent):
                    # Finalize streaming text
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    iter_count += 1
                    args_str = _fmt_args(event.args)
                    console.print(Text.assemble(
                        ("  ↳ ", "dim"),
                        (event.tool, "bold yellow"),
                        (f"({args_str})", "yellow"),
                    ))
                elif isinstance(event, ObservationEvent):
                    icon = "✗" if event.is_error else "✓"
                    color = "red" if event.is_error else "green"
                    output = event.output.strip()
                    if len(output) > 500:
                        output = output[:250] + f"\n  …(+{len(output)-500} chars)" + output[-250:]
                    lines = output.splitlines()
                    if len(lines) > 6:
                        output = "\n".join(lines[:5]) + f"\n  …(+{len(lines)-5} more lines)"
                    for line in output.splitlines():
                        console.print(Text(f"    {icon} {line}", style=color))
                elif isinstance(event, AgentErrorEvent):
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    console.print(Text.assemble(
                        ("  ✗ ", "bold red"),
                        (event.message[:500], "red"),
                    ))
                elif isinstance(event, FinishEvent):
                    if streaming_active and streaming_text:
                        _render_assistant(streaming_text)
                        streaming_text = ""
                        streaming_active = False
                    if event.reason != "completed":
                        console.print(f"  [dim]finished: {event.reason}[/]")
        except Exception as e:
            if streaming_active and streaming_text:
                _render_assistant(streaming_text)
            console.print(f"  [bold red]✗ Fatal error:[/] {type(e).__name__}: {e}")

        console.print()  # blank line between turns


def _render_assistant(content: str) -> None:
    """Render an assistant message as markdown."""
    if not content.strip():
        console.print("  [dim](empty response)[/]")
        return
    console.print(Text.assemble(("HELIX", "bold blue"), (":", "dim")))
    try:
        console.print(Markdown(content))
    except Exception:
        console.print(Text(content, "white"))


def _handle_slash(cmd: str, arg: str, config: HelixConfig, conv: Conversation) -> bool:
    """Handle slash command. Returns True if should exit."""
    if cmd in ("exit", "quit"):
        console.print("[dim]Bye.[/]")
        return True
    elif cmd == "help":
        console.print(Panel(
            "[bold]Commands:[/]\n"
            "  [cyan]/help[/]        show this help\n"
            "  [cyan]/skills[/]      list all skills\n"
            "  [cyan]/memory[/]      show memory files\n"
            "  [cyan]/tools[/]       list all tools\n"
            "  [cyan]/sessions[/]    list past sessions\n"
            "  [cyan]/status[/]      show current config\n"
            "  [cyan]/test[/]        test LLM connection\n"
            "  [cyan]/models[/]      list models on gateway\n"
            "  [cyan]/exit[/]        quit HELIX",
            title="Help", border_style="blue"))
    elif cmd == "skills":
        skills = load_skill_summaries(config.home)
        if not skills:
            console.print("[dim](no skills yet — agent creates them after tasks)[/]")
        for s in skills:
            console.print(f"  [bold green]{s['name']}[/]: {s['description']}")
    elif cmd == "memory":
        mem = load_memory(config.home)
        for kind in ("IDENTITY", "USER", "MEMORY"):
            if kind in mem:
                console.print(Panel(mem[kind], title=kind, border_style="magenta"))
    elif cmd == "tools":
        tools = all_tools(config)
        for t in tools:
            danger = " [red]⚠[/]" if t.dangerous else ""
            ro = " [green]ro[/]" if t.read_only else ""
            console.print(f"  [bold yellow]{t.name}[/]{danger}{ro} — {t.description[:80]}")
    elif cmd == "sessions":
        sd = config.home / "sessions"
        for f in sorted(sd.glob("*.jsonl")):
            console.print(f"  {f.stem}")
    elif cmd == "status":
        console.print(Panel.fit(
            f"[bold]HELIX Status[/]\n\n"
            f"[dim]Home:[/]     {config.home}\n"
            f"[dim]Provider:[/] {config.provider}\n"
            f"[dim]Model:[/]    {config.model}\n"
            f"[dim]Base URL:[/] {config.base_url or '(provider default)'}\n"
            f"[dim]API key:[/]  {'✓ set' if config.api_key else '[red]✗ NOT SET[/]'}\n"
            f"[dim]On Termux:[/] {config.on_termux}\n"
            f"[dim]Tools:[/]    {len(all_tools(config))} registered\n"
            f"[dim]Session:[/]  {conv.session_id}",
            border_style="blue"))
    elif cmd == "test":
        _run_test(config)
    elif cmd == "models":
        _run_list_models(config)
    elif cmd == "new":
        console.print("[dim]Start a new session by exiting (Ctrl+C or /exit) and running 'helix tui' again.[/]")
    else:
        console.print(f"[red]Unknown command: /{cmd}[/] (try /help)")
    return False


def _run_test(config: HelixConfig) -> None:
    """Test LLM connection — same as /api/test_llm in the web UI."""
    from ..llm import get_llm
    console.print(f"[dim]Testing {config.provider}/{config.model} at {config.base_url or '(default)'}...[/]")
    try:
        llm = get_llm(config)
        import asyncio
        async def _do():
            return await llm.complete(
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                tools=None,
                system="You are a test. Reply with OK.",
            )
        resp = asyncio.get_event_loop().run_until_complete(_do())
        if resp.finish_reason == "error":
            console.print(f"[bold red]✗ Failed[/]")
            if isinstance(resp.raw, dict):
                console.print(f"  [red]Error:[/] {resp.raw.get('error', '')[:400]}")
                if resp.raw.get("status"):
                    console.print(f"  [dim]HTTP status:[/] {resp.raw['status']}")
                if resp.raw.get("url"):
                    console.print(f"  [dim]URL:[/] {resp.raw['url']}")
                if resp.raw.get("hint"):
                    console.print(f"  [blue]Hint:[/] {resp.raw['hint']}")
        else:
            console.print(f"[bold green]✓ Works![/]  Model replied: [cyan]{resp.content}[/]")
            if resp.usage:
                console.print(f"  [dim]Tokens:[/] {resp.usage}")
    except Exception as e:
        console.print(f"[bold red]✗ Error:[/] {type(e).__name__}: {e}")


def _run_list_models(config: HelixConfig) -> None:
    """List models on the gateway."""
    import httpx
    if not config.base_url:
        console.print("[red]No base_url set. Set HELIX_BASE_URL first.[/]")
        return
    url = config.base_url.rstrip("/") + "/models"
    console.print(f"[dim]Fetching {url}...[/]")
    try:
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        r = httpx.get(url, headers=headers, timeout=15)
        if r.status_code >= 400:
            console.print(f"[red]✗ HTTP {r.status_code}[/]")
            console.print(f"  {r.text[:400]}")
            return
        data = r.json()
        models = []
        if isinstance(data, dict) and "data" in data:
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
        elif isinstance(data, list):
            for m in data:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
                elif isinstance(m, str):
                    models.append(m)
        models.sort()
        console.print(f"[green]✓ {len(models)} models on your gateway:[/]")
        if arg_filter := "":
            for m in models:
                console.print(f"  [yellow]{m}[/]")
        # Print in columns
        if len(models) > 20:
            console.print(f"  [dim](showing first 30, use /models <filter> to narrow)[/]")
            for m in models[:30]:
                console.print(f"  [yellow]{m}[/]")
        else:
            for m in models:
                console.print(f"  [yellow]{m}[/]")
    except Exception as e:
        console.print(f"[red]✗ Error:[/] {type(e).__name__}: {e}")
