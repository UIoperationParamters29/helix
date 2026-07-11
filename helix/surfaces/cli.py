"""HELIX CLI — interactive terminal interface."""
from __future__ import annotations

import asyncio, sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.live import Live
from rich.text import Text

from ..config import HelixConfig, get_helix_home
from ..conversation import Conversation
from ..events import (
    Event, MessageEvent, ActionEvent, ObservationEvent,
    AgentErrorEvent, FinishEvent,
)
from ..memory.manager import init_memory_files
from ..tools import all_tools


console = Console()


def _event_panel(event: Event) -> Panel | None:
    """Render an event as a Rich panel."""
    if isinstance(event, MessageEvent):
        if event.role == "user":
            return Panel(Text(event.content, style="bold cyan"),
                         title="[bold cyan]You[/]", border_style="cyan")
        elif event.role == "assistant":
            return Panel(Markdown(event.content),
                         title="[bold blue]HELIX[/]", border_style="blue")
    elif isinstance(event, ActionEvent):
        args_str = ", ".join(f"{k}={v!r}" for k, v in event.args.items())
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        return Panel(
            Text(f"{event.tool}({args_str})", style="yellow"),
            title=f"[bold yellow]Tool Call[/] — {event.tool}",
            border_style="yellow",
        )
    elif isinstance(event, ObservationEvent):
        style = "red" if event.is_error else "green"
        icon = "✗" if event.is_error else "✓"
        text = event.output
        if len(text) > 2000:
            text = text[:1000] + f"\n[...{len(text)-2000} chars truncated...]\n" + text[-1000:]
        return Panel(
            Text(text, style=style),
            title=f"[{style}]{icon} Result[/] — {event.tool}",
            border_style=style,
        )
    elif isinstance(event, AgentErrorEvent):
        return Panel(Text(event.message, style="bold red"),
                     title="[bold red]Error[/]", border_style="red")
    elif isinstance(event, FinishEvent):
        return Panel(Text(f"Done ({event.reason})", style="dim"),
                     border_style="dim")
    return None


async def chat_loop(config: HelixConfig):
    """Interactive REPL."""
    init_memory_files(config.home, config.persona)
    session_id = None
    conv = Conversation(config=config, session_id=session_id)

    console.print(Panel.fit(
        f"[bold blue]HELIX[/] [dim]v0.1.0[/]\n"
        f"[dim]Provider:[/] [cyan]{config.provider}[/] [dim]Model:[/] [cyan]{config.model}[/]\n"
        f"[dim]Home:[/] {config.home}\n"
        f"[dim]Tools:[/] {len(all_tools(config))} registered  "
        f"[dim]Termux:[/] {'yes' if config.on_termux else 'no'}\n"
        f"[dim]Type [bold]/help[/] for commands, [bold]/exit[/] to quit.[/]",
        border_style="blue",
    ))

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: console.input("[bold cyan]›[/] ")
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/]")
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            cmd = user_input[1:].lower()
            if cmd in ("exit", "quit"):
                console.print("[dim]Bye.[/]")
                return
            elif cmd == "help":
                console.print(Panel(
                    "[bold]/help[/] — show this help\n"
                    "[bold]/tools[/] — list available tools\n"
                    "[bold]/skills[/] — list skills\n"
                    "[bold]/memory[/] — show memory files\n"
                    "[bold]/sessions[/] — list past sessions\n"
                    "[bold]/new[/] — start new session\n"
                    "[bold]/exit[/] — quit HELIX",
                    title="Commands", border_style="blue"))
                continue
            elif cmd == "tools":
                tools = all_tools(config)
                for t in tools:
                    danger = " [red](dangerous)[/]" if t.dangerous else ""
                    console.print(f"  [bold yellow]{t.name}[/]{danger} — {t.description[:80]}")
                continue
            elif cmd == "skills":
                from ..skills.loader import load_skill_summaries
                skills = load_skill_summaries(config.home)
                if not skills:
                    console.print("[dim](no skills yet)[/]")
                for s in skills:
                    console.print(f"  [bold green]{s['name']}[/]: {s['description']}")
                continue
            elif cmd == "memory":
                from ..memory.manager import load_memory
                mem = load_memory(config.home)
                for kind, text in mem.items():
                    console.print(Panel(text, title=kind, border_style="magenta"))
                continue
            elif cmd == "sessions":
                sd = config.home / "sessions"
                for f in sorted(sd.glob("*.jsonl")):
                    console.print(f"  {f.stem}")
                continue
            elif cmd == "new":
                conv = Conversation(config=config)
                console.print("[green]New session started.[/]")
                continue
            else:
                console.print(f"[red]Unknown command: /{cmd}[/]")
                continue

        # Normal message
        try:
            async for event in conv.send(user_input):
                panel = _event_panel(event)
                if panel:
                    console.print(panel)
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")


@click.group()
def cli():
    """HELIX — self-improving agent harness."""
    pass


@cli.command()
@click.option("--provider", default=None, help="LLM provider (openai, anthropic, zai, ollama, lmstudio).")
@click.option("--model", default=None, help="Model name.")
@click.option("--base-url", default=None, help="OpenAI-compatible base URL.")
def chat(provider, model, base_url):
    """Start an interactive chat session."""
    config = HelixConfig.load()
    if provider: config.provider = provider
    if model: config.model = model
    if base_url: config.base_url = base_url
    asyncio.run(chat_loop(config))


@cli.command()
def setup():
    """Run first-time setup."""
    config = HelixConfig.load()
    init_memory_files(config.home, config.persona)
    console.print(f"[green]HELIX_HOME:[/] {config.home}")
    console.print(f"[green]Memory files initialized.[/]")
    console.print(f"\nNext steps:")
    console.print(f"  1. Set your API key:  [cyan]export OPENAI_API_KEY=sk-...[/]")
    console.print(f"  2. Edit config:       [cyan]{config.home / 'config.yaml'}[/]")
    console.print(f"  3. Start chatting:    [cyan]helix chat[/]")


@cli.command()
def status():
    """Show current configuration."""
    config = HelixConfig.load()
    console.print(Panel.fit(
        f"[bold]HELIX Status[/]\n\n"
        f"[dim]Home:[/]     {config.home}\n"
        f"[dim]Provider:[/] {config.provider}\n"
        f"[dim]Model:[/]    {config.model}\n"
        f"[dim]API key:[/]  {'set' if config.api_key else '[red]NOT SET[/]'}\n"
        f"[dim]Base URL:[/] {config.base_url or '(provider default)'}\n"
        f"[dim]On Termux:[/] {config.on_termux}\n"
        f"[dim]Tools:[/]    {len(all_tools(config))} registered\n",
        border_style="blue",
    ))


@cli.command()
def tools():
    """List all available tools."""
    config = HelixConfig.load()
    for t in all_tools(config):
        danger = " [red](dangerous)[/]" if t.dangerous else ""
        ro = " [green](read-only)[/]" if t.read_only else ""
        console.print(f"\n[bold yellow]{t.name}[/]{danger}{ro}")
        console.print(f"  {t.description}")


@cli.command()
@click.option("--host", default=None)
@click.option("--port", default=None, type=int)
def web(host, port):
    """Start the web UI server (FastAPI + WebSocket)."""
    config = HelixConfig.load()
    if host: config.web_host = host
    if port: config.web_port = port
    from .web_api.server import run_server
    run_server(config)


def main():
    cli()


if __name__ == "__main__":
    main()
