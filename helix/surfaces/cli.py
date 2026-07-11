"""HELIX CLI — commands dispatcher.

Thin layer: each command delegates to its implementation module.
  helix chat     → surfaces.chat_loop
  helix tui      → surfaces.tui
  helix web      → surfaces.web_api.server
  helix doctor   → surfaces.doctor
  helix adb      → surfaces.adb_setup
  helix tools    → tools.all_tools
  helix status   → config dump
  helix setup    → init memory files
"""
from __future__ import annotations

import asyncio, os
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

from ..config import HelixConfig
from ..conversation import Conversation
from ..events import Event, MessageEvent, ActionEvent, ObservationEvent, AgentErrorEvent, FinishEvent
from ..memory.manager import init_memory_files
from ..tools import all_tools

console = Console()


def _fmt_args(args: dict, max_len: int = 100) -> str:
    """Compact arg formatting."""
    parts = []
    for k, v in args.items():
        vs = v if isinstance(v, str) and len(v) <= 60 else (repr(v) if not isinstance(v, str) else v[:57] + "...")
        if isinstance(vs, str) and len(vs) > 60:
            vs = vs[:57] + "..."
        parts.append(f"{k}={vs}")
    s = ", ".join(parts)
    return s[:max_len] + "..." if len(s) > max_len else s


# ─── Chat loop (classic REPL with streaming) ─────────────────────────────

async def chat_loop(config: HelixConfig):
    """Interactive REPL."""
    init_memory_files(config.home, config.persona)
    conv = Conversation(config=config)

    console.print(Panel.fit(
        f"[bold blue]HELIX[/] [dim]v0.1.0[/]\n"
        f"[dim]Model:[/] [cyan]{config.model}[/]  [dim]URL:[/] {config.base_url or '(default)'}\n"
        f"[dim]API key:[/] {'✓' if config.api_key else '[red]✗ NOT SET[/]'}  "
        f"[dim]Tools:[/] {len(all_tools(config))}\n"
        f"[dim]Type [bold]/help[/] for commands, [bold]/exit[/] to quit.[/]",
        border_style="blue",
    ))

    if not config.api_key:
        console.print("[red]⚠ No API key![/]  [cyan]export HELIX_API_KEY=your_key[/]\n")

    while True:
        try:
            user_input = console.input("[bold cyan]›[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/]")
            return

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            cmd = user_input[1:].split()[0].lower() if user_input[1:].split() else ""
            if cmd in ("exit", "quit"):
                return
            elif cmd == "help":
                console.print("  [bold]/help[/]    show commands")
                console.print("  [bold]/skills[/]  list skills")
                console.print("  [bold]/memory[/]  show memory")
                console.print("  [bold]/tools[/]   list tools")
                console.print("  [bold]/exit[/]    quit")
            elif cmd == "skills":
                from ..skills.loader import load_skill_summaries
                for s in load_skill_summaries(config.home):
                    console.print(f"  [green]{s['name']}[/]: {s['description']}")
            elif cmd == "memory":
                from ..memory.manager import load_memory
                for kind, text in load_memory(config.home).items():
                    console.print(Panel(text, title=kind, border_style="magenta"))
            elif cmd == "tools":
                for t in all_tools(config):
                    console.print(f"  [yellow]{t.name}[/] — {t.description[:80]}")
            else:
                console.print(f"[red]Unknown: /{cmd}[/]")
            continue

        # Send to agent
        try:
            streaming_text = ""
            streaming_active = False
            async for event in conv.send_streaming(user_input):
                if isinstance(event, MessageEvent) and event.role == "assistant":
                    streaming_active = True
                    streaming_text = event.content
                elif isinstance(event, ActionEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text), title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_active = False
                    console.print(Panel(
                        Text(f"{event.tool}({_fmt_args(event.args)})", style="yellow"),
                        title=f"[bold yellow]↳ {event.tool}[/]", border_style="yellow",
                    ))
                elif isinstance(event, ObservationEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text), title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_active = False
                    style = "red" if event.is_error else "green"
                    icon = "✗" if event.is_error else "✓"
                    text = event.output[:2000] + ("..." if len(event.output) > 2000 else "")
                    console.print(Panel(Text(text, style=style),
                                        title=f"[{style}]{icon} {event.tool}[/]", border_style=style))
                elif isinstance(event, AgentErrorEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text), title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_active = False
                    console.print(Panel(Text(event.message, style="bold red"),
                                        title="[bold red]✗ Error[/]", border_style="red"))
                elif isinstance(event, FinishEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text), title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_active = False
            if streaming_active and streaming_text:
                console.print(Panel(Markdown(streaming_text), title="[bold blue]HELIX[/]", border_style="blue"))
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Interrupted.[/]")
        except Exception as e:
            console.print(f"[bold red]✗ Error:[/] {e}")


# ─── Click commands ──────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """HELIX — self-improving agent harness.

    Run 'helix' with no arguments to launch the TUI.
    Run 'helix --help' to see all commands.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand → launch TUI
        config = HelixConfig.load()
        from .tui import tui_main
        try:
            asyncio.run(tui_main(config))
        except KeyboardInterrupt:
            pass


@cli.command()
@click.option("--provider", default=None)
@click.option("--model", default=None)
@click.option("--base-url", default=None)
def chat(provider, model, base_url):
    """Interactive chat (classic REPL mode)."""
    config = HelixConfig.load()
    if provider: config.provider = provider
    if model: config.model = model
    if base_url: config.base_url = base_url
    try:
        asyncio.run(chat_loop(config))
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option("--provider", default=None)
@click.option("--model", default=None)
@click.option("--base-url", default=None)
def tui(provider, model, base_url):
    """Full-screen TUI (Hermes-style)."""
    config = HelixConfig.load()
    if provider: config.provider = provider
    if model: config.model = model
    if base_url: config.base_url = base_url
    from .tui import tui_main
    try:
        asyncio.run(tui_main(config))
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def web(host, port):
    """Start the web UI server."""
    config = HelixConfig.load()
    if host: config.web_host = host
    if port: config.web_port = port
    from .web_api.server import run_server
    try:
        run_server(config)
    except KeyboardInterrupt:
        print("\nStopped.")


@cli.command()
def doctor():
    """Diagnose your setup."""
    from .doctor import run_doctor
    run_doctor()


@cli.command()
def adb():
    """Set up self-ADB pairing for phone UI control."""
    from .adb_setup import run_adb_setup
    try:
        run_adb_setup()
    except KeyboardInterrupt:
        print("\nAborted.")


@cli.command()
def setup():
    """First-time setup."""
    config = HelixConfig.load()
    init_memory_files(config.home, config.persona)
    console.print(f"[green]HELIX_HOME:[/] {config.home}")
    console.print(f"[green]Memory files initialized.[/]")
    console.print(f"\nNext steps:")
    console.print(f"  1. Set API key:  [cyan]export HELIX_API_KEY=sk-...[/]")
    console.print(f"  2. Edit config:  [cyan]{config.home / 'config.yaml'}[/]")
    console.print(f"  3. Start:        [cyan]helix web[/] or [cyan]helix tui[/]")


@cli.command()
def status():
    """Show current configuration."""
    config = HelixConfig.load()
    console.print(Panel.fit(
        f"[bold]HELIX Status[/]\n\n"
        f"[dim]Home:[/]      {config.home}\n"
        f"[dim]Provider:[/]  {config.provider}\n"
        f"[dim]Model:[/]     {config.model}\n"
        f"[dim]Base URL:[/]  {config.base_url or '(default)'}\n"
        f"[dim]API key:[/]   {'✓ set' if config.api_key else '[red]✗ NOT SET[/]'}\n"
        f"[dim]Termux:[/]    {config.on_termux}\n"
        f"[dim]Tools:[/]     {len(all_tools(config))} registered",
        border_style="blue",
    ))


@cli.command()
def model():
    """Switch model/provider interactively (like Hermes 'hermes model').

    Shows current model, lists saved providers, lets you add new providers,
    pick models from the gateway, and test connections.
    """
    from .model_switcher import run_model_switcher
    try:
        run_model_switcher()
    except KeyboardInterrupt:
        print("\nAborted.")


@cli.command()
def tools():
    """List all available tools."""
    config = HelixConfig.load()
    for t in all_tools(config):
        danger = " [red]⚠[/]" if t.dangerous else ""
        ro = " [green]ro[/]" if t.read_only else ""
        console.print(f"  [bold yellow]{t.name}[/]{danger}{ro} — {t.description[:80]}")


def main():
    try:
        cli()
    except KeyboardInterrupt:
        print("\nAborted.")


if __name__ == "__main__":
    main()
