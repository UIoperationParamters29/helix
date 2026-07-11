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


def _format_tool_args(tool: str, args: dict) -> str:
    """Format tool arguments compactly for display."""
    # Hide verbose args
    hidden_keys = {"content", "text", "message", "command"}
    parts = []
    for k, v in args.items():
        vs = repr(v) if not isinstance(v, str) else v
        if k in hidden_keys and len(vs) > 60:
            vs = vs[:57] + "..."
        elif len(vs) > 80:
            vs = vs[:77] + "..."
        parts.append(f"{k}={vs}")
    return ", ".join(parts)


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
        args_str = _format_tool_args(event.tool, event.args)
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

        # Normal message — use streaming for live text
        try:
            streaming_text = ""
            streaming_active = False
            async for event in conv.send_streaming(user_input):
                if isinstance(event, MessageEvent) and event.role == "assistant":
                    if not streaming_active:
                        streaming_active = True
                        streaming_text = event.content
                    else:
                        streaming_text = event.content
                elif isinstance(event, ActionEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text),
                                             title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_text = ""
                        streaming_active = False
                    args_str = _format_tool_args(event.tool, event.args)
                    console.print(Panel(
                        Text(f"{event.tool}({args_str})", style="yellow"),
                        title=f"[bold yellow]Tool Call[/] — {event.tool}",
                        border_style="yellow",
                    ))
                elif isinstance(event, ObservationEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text),
                                             title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_text = ""
                        streaming_active = False
                    style = "red" if event.is_error else "green"
                    icon = "✗" if event.is_error else "✓"
                    text = event.output
                    if len(text) > 2000:
                        text = text[:1000] + f"\n[...{len(text)-2000} chars truncated...]\n" + text[-1000:]
                    console.print(Panel(
                        Text(text, style=style),
                        title=f"[{style}]{icon} Result[/] — {event.tool}",
                        border_style=style,
                    ))
                elif isinstance(event, AgentErrorEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text),
                                             title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_text = ""
                        streaming_active = False
                    console.print(Panel(Text(event.message, style="bold red"),
                                         title="[bold red]Error[/]", border_style="red"))
                elif isinstance(event, FinishEvent):
                    if streaming_active and streaming_text:
                        console.print(Panel(Markdown(streaming_text),
                                             title="[bold blue]HELIX[/]", border_style="blue"))
                        streaming_text = ""
                        streaming_active = False
                # Skip user message events (we already echoed the input)
            # Final flush
            if streaming_active and streaming_text:
                console.print(Panel(Markdown(streaming_text),
                                     title="[bold blue]HELIX[/]", border_style="blue"))
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
    """Start an interactive chat session (classic REPL mode)."""
    config = HelixConfig.load()
    if provider: config.provider = provider
    if model: config.model = model
    if base_url: config.base_url = base_url
    asyncio.run(chat_loop(config))


@cli.command()
@click.option("--provider", default=None, help="LLM provider (openai, anthropic, zai, ollama, lmstudio).")
@click.option("--model", default=None, help="Model name.")
@click.option("--base-url", default=None, help="OpenAI-compatible base URL.")
def tui(provider, model, base_url):
    """Launch the full-screen TUI (Hermes-style multi-pane interface).

    Multi-pane layout: header / chat / sidebar (skills+memory+tools) / input.
    Alternate-screen rendering — no scrollback clutter.
    Slash commands: /help /skills /memory /tools /exit
    """
    config = HelixConfig.load()
    if provider: config.provider = provider
    if model: config.model = model
    if base_url: config.base_url = base_url
    from .tui import tui_main
    asyncio.run(tui_main(config))


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


@cli.command()
def doctor():
    """Diagnose your HELIX setup. Shows config source, tests LLM, lists models.

    Run this first if anything is broken. It tells you exactly what's wrong
    and how to fix it.
    """
    import os, asyncio
    config = HelixConfig.load()

    console.print(Panel.fit(
        "[bold]HELIX Doctor[/] — diagnosing your setup\n"
        "[dim]This will show your config, test the LLM connection, and list models.[/]",
        border_style="blue",
    ))

    # 1. Config sources
    console.print("\n[bold]1. Configuration[/]")
    console.print(f"   HELIX_HOME:    {config.home}")
    config_file = config.home / "config.yaml"
    console.print(f"   Config file:   {config_file} [{'✓ exists' if config_file.exists() else '✗ missing'}]")
    console.print(f"   Provider:      {config.provider}")
    console.print(f"   Model:         {config.model}")
    console.print(f"   Base URL:      {config.base_url or '(provider default)'}")
    console.print(f"   API key:       {'✓ set (' + config.api_key[:8] + '...)' if config.api_key else '✗ NOT SET'}")
    console.print(f"   On Termux:     {config.on_termux}")
    console.print(f"   Tools:         {len(all_tools(config))} registered")

    # Show which env vars are set
    console.print("\n[bold]2. Environment variables[/]")
    for var in ("HELIX_PROVIDER", "HELIX_MODEL", "HELIX_BASE_URL", "HELIX_API_KEY",
                "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        val = os.environ.get(var)
        if val:
            display = val[:12] + "..." if var.endswith("KEY") and len(val) > 12 else val
            console.print(f"   {var}={display} [green](set)[/]")
        else:
            console.print(f"   {var} [dim](not set)[/]")

    # 3. Common issues
    console.print("\n[bold]3. Common issues check[/]")
    issues = []
    if not config.api_key:
        issues.append(("red", "No API key set", "export HELIX_API_KEY=your_key"))
    if config.base_url and not config.base_url.rstrip('/').endswith('/v1') and 'openai.com' not in (config.base_url or ''):
        if 'gateway' in (config.base_url or '').lower() or 'api.' in (config.base_url or '').lower():
            issues.append(("yellow", f"base_url doesn't end with /v1 (most gateways need it)",
                          f"export HELIX_BASE_URL={config.base_url.rstrip('/')}/v1"))
    if not issues:
        console.print("   [green]✓ No obvious issues found[/]")
    else:
        for color, msg, fix in issues:
            console.print(f"   [{color}]⚠ {msg}[/]")
            console.print(f"      [dim]Fix:[/] [cyan]{fix}[/]")

    # 4. Test LLM connection
    if config.api_key:
        console.print("\n[bold]4. Testing LLM connection...[/]")
        from ..llm import get_llm
        try:
            llm = get_llm(config)
            async def _test():
                return await llm.complete(
                    messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                    tools=None,
                    system="You are a test. Reply with OK.",
                )
            resp = asyncio.run(_test())
            if resp.finish_reason == "error":
                console.print(f"   [bold red]✗ LLM test failed[/]")
                if isinstance(resp.raw, dict):
                    console.print(f"   [red]Error:[/] {str(resp.raw.get('error', ''))[:300]}")
                    if resp.raw.get("status"):
                        console.print(f"   [dim]HTTP status:[/] {resp.raw['status']}")
                    if resp.raw.get("url"):
                        console.print(f"   [dim]URL hit:[/] {resp.raw['url']}")
                    if resp.raw.get("hint"):
                        console.print(f"   [blue]Hint:[/] {resp.raw['hint']}")
            else:
                console.print(f"   [bold green]✓ LLM works![/]  Model replied: [cyan]{resp.content}[/]")
        except Exception as e:
            console.print(f"   [bold red]✗ Error:[/] {type(e).__name__}: {e}")

    # 5. List models
    if config.api_key and config.base_url:
        console.print("\n[bold]5. Listing models on gateway...[/]")
        import httpx
        url = config.base_url.rstrip("/") + "/models"
        try:
            headers = {"Authorization": f"Bearer {config.api_key}"}
            r = httpx.get(url, headers=headers, timeout=15)
            if r.status_code >= 400:
                console.print(f"   [red]✗ HTTP {r.status_code}: {r.text[:200]}[/]")
            else:
                data = r.json()
                models = []
                if isinstance(data, dict) and "data" in data:
                    for m in data["data"]:
                        if isinstance(m, dict) and "id" in m:
                            models.append(m["id"])
                models.sort()
                console.print(f"   [green]✓ {len(models)} models available[/]")
                console.print(f"   [dim]First 15:[/]")
                for m in models[:15]:
                    marker = " ← current" if m == config.model else ""
                    console.print(f"     [yellow]{m}[/]{marker}")
                if len(models) > 15:
                    console.print(f"     [dim]...and {len(models) - 15} more[/]")
                # Check if current model is in the list
                if config.model not in models:
                    console.print(f"\n   [bold red]⚠ Your model '{config.model}' is NOT in the gateway's model list![/]")
                    console.print(f"   [dim]Pick one from the list above and:[/]")
                    console.print(f"   [cyan]export HELIX_MODEL=<one_from_above>[/]")
        except Exception as e:
            console.print(f"   [red]✗ Error: {type(e).__name__}: {e}[/]")

    console.print("\n[bold]Done.[/] If issues found, fix the env vars and run [cyan]helix doctor[/] again.")


@cli.command()
def config_show():
    """Show current configuration (alias: helix doctor without the tests)."""
    import os
    config = HelixConfig.load()
    console.print(Panel.fit(
        f"[bold]HELIX Config[/]\n\n"
        f"[dim]Home:[/]       {config.home}\n"
        f"[dim]Provider:[/]   {config.provider}\n"
        f"[dim]Model:[/]      {config.model}\n"
        f"[dim]Base URL:[/]   {config.base_url or '(provider default)'}\n"
        f"[dim]API key:[/]    {'✓ set' if config.api_key else '[red]✗ NOT SET[/]'}\n"
        f"[dim]On Termux:[/]  {config.on_termux}\n"
        f"[dim]Tools:[/]      {len(all_tools(config))} registered\n"
        f"[dim]Max iters:[/]  {config.max_iterations}\n"
        f"[dim]Auto-approve reads:[/]  {config.auto_approve_reads}\n"
        f"[dim]Auto-approve writes:[/] {config.auto_approve_writes}\n",
        border_style="blue",
    ))
    console.print("\n[dim]Env overrides (these take priority over config.yaml):[/]")
    for var in ("HELIX_PROVIDER", "HELIX_MODEL", "HELIX_BASE_URL", "HELIX_API_KEY"):
        val = os.environ.get(var)
        if val:
            console.print(f"  [green]{var}={val[:20]}{'...' if len(val)>20 else ''}[/]")


@cli.command()
def adb():
    """Set up self-ADB pairing for phone UI control (tap, swipe, type, screenshot).

    This lets HELIX control your phone's screen — tap buttons, type text,
    take screenshots, launch apps. Works WITHOUT root.

    Prerequisites:
      - Android 11+
      - Termux with android-tools installed (pkg install android-tools)
      - Wireless debugging enabled in Developer Options

    Run this command and follow the prompts. It will guide you through
    pairing your phone to itself via wireless ADB.
    """
    import shutil, subprocess, os, re
    console.print(Panel.fit(
        "[bold]HELIX Self-ADB Setup[/]\n"
        "[dim]Pair your phone to itself for full UI control[/]",
        border_style="blue",
    ))

    # Check if we're on Termux
    config = HelixConfig.load()
    if not config.on_termux:
        console.print("[yellow]⚠ Not running on Termux.[/]")
        console.print("  Self-ADB pairing is for Android phones running HELIX in Termux.")
        console.print("  On PC, you can still control a phone via USB ADB:")
        console.print("    1. Install platform-tools: https://developer.android.com/tools/releases/platform-tools")
        console.print("    2. Enable USB debugging on your phone")
        console.print("    3. Connect via USB")
        console.print("    4. Run: adb devices")
        console.print()
        console.print("  To run the pairing script anyway (if you're on Termux but detection failed):")
        script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "setup_adb.sh")
        console.print(f"    bash {os.path.abspath(script)}")
        return

    # Check if adb is installed
    if not shutil.which("adb"):
        console.print("[yellow]⚠ adb not found. Installing android-tools...[/]")
        subprocess.run(["pkg", "install", "-y", "android-tools"])

    if not shutil.which("adb"):
        console.print("[red]✗ Failed to install android-tools. Run: pkg install android-tools[/]")
        return

    console.print("[green]✓ adb is available[/]")
    console.print()

    # Helper: read from clipboard if termux-clipboard-get is available
    def get_clipboard() -> str:
        try:
            r = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        return ""

    # Helper: parse "IP:port" from a string (user might paste extra text)
    def parse_addr(s: str) -> str | None:
        # Match 192.168.1.42:37123 or [::1]:37123
        m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{4,5})', s)
        if m:
            return m.group(1)
        # IPv6
        m = re.search(r'(\[[0-9a-fA-F:]+\]:\d{4,5})', s)
        if m:
            return m.group(1)
        return None

    # Helper: parse 6-digit code from a string
    def parse_code(s: str) -> str | None:
        m = re.search(r'\b(\d{6})\b', s)
        if m:
            return m.group(1)
        return None

    # Helper: prompt with clipboard option
    def prompt_with_clipboard(label: str, parser, example: str) -> str | None:
        """Ask user for input, offering to use clipboard contents."""
        console.print(f"  [bold]{label}[/]")
        console.print(f"  [dim]Example: {example}[/]")
        console.print(f"  [dim]Type it, or press 'c' + Enter to paste from clipboard[/]")
        console.print()
        while True:
            try:
                val = input("  › ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not val:
                console.print("  [red]Empty input. Try again or Ctrl+C to abort.[/]")
                continue
            if val.lower() in ("c", "clip", "paste"):
                clip = get_clipboard()
                if clip:
                    console.print(f"  [dim]Clipboard contents:[/]")
                    console.print(f"  [cyan]{clip[:200]}[/]")
                    parsed = parser(clip)
                    if parsed:
                        console.print(f"  [green]✓ Found: {parsed}[/]")
                        return parsed
                    else:
                        console.print("  [yellow]Couldn't parse from clipboard. Type manually:[/]")
                        continue
                else:
                    console.print("  [yellow]Clipboard empty or termux-clipboard-get not available.[/]")
                    console.print("  [dim]Install with: pkg install termux-api[/]")
                    continue
            # Try to parse what they typed
            parsed = parser(val)
            if parsed:
                return parsed
            # If no parse, return as-is (might be valid format we didn't match)
            return val

    # --- Step 1: Enable Wireless debugging ---
    console.print("[bold cyan]Step 1: Enable Wireless debugging[/]")
    console.print("  Go to: [dim]Settings → System → Developer Options → Wireless debugging[/]")
    console.print("  [dim](If you don't see Developer Options, tap 'Build Number' 7x in About Phone)[/]")
    console.print("  [dim]Toggle it ON.[/]")
    console.print()
    try:
        input("  Press Enter when done...")
    except (EOFError, KeyboardInterrupt):
        return
    console.print()

    # --- Step 2: Pair ---
    console.print("[bold cyan]Step 2: Pair your device[/]")
    console.print("  In Wireless debugging settings, tap [bold]'Pair device with pairing code'[/]")
    console.print("  A dialog appears showing:")
    console.print("    • Wi-Fi pairing code: [bold green]6 digits[/]")
    console.print("    • IP address & port: [bold green]192.168.x.x:xxxxx[/]")
    console.print()
    console.print("  [yellow]💡 Tip: Copy the IP:port to your clipboard before continuing.[/]")
    console.print("     Long-press the IP:port text on the pairing screen → Copy.")
    console.print("     Then type 'c' at the prompt below to paste.")
    console.print()

    pair_addr = prompt_with_clipboard(
        "Enter the pairing IP:port",
        parse_addr,
        "192.168.1.42:37123"
    )
    if not pair_addr:
        console.print("[red]Aborted.[/]")
        return

    pair_code = prompt_with_clipboard(
        "Enter the 6-digit pairing code",
        parse_code,
        "123456"
    )
    if not pair_code:
        console.print("[red]Aborted.[/]")
        return

    console.print()
    console.print(f"[dim]Pairing with {pair_addr} using code {pair_code}...[/]")

    # Use subprocess.run with input= instead of shell here-string (<<<)
    # The <<< syntax is bash-only; Termux's /bin/sh is dash which doesn't support it.
    try:
        proc = subprocess.run(
            ["adb", "pair", pair_addr],
            input=pair_code + "\n",
            capture_output=True,
            text=True,
            timeout=30,
        )
        # adb pair prints to stdout+stderr
        output = (proc.stdout or "") + (proc.stderr or "")
        console.print(f"  [dim]{output.strip()}[/]")
        if proc.returncode != 0:
            console.print(f"[red]✗ Pairing failed (exit {proc.returncode}).[/]")
            console.print("  Common causes:")
            console.print("    • Pairing dialog was closed (it times out in ~30s)")
            console.print("    • Wrong IP:port (use the PAIRING port, not the connection port)")
            console.print("    • Wrong code")
            console.print("    • Different WiFi network")
            console.print()
            console.print("  [dim]Re-open the pairing dialog and try again.[/]")
            return
    except subprocess.TimeoutExpired:
        console.print("[red]✗ Pairing timed out. The pairing dialog may have closed.[/]")
        return
    except Exception as e:
        console.print(f"[red]✗ Error: {type(e).__name__}: {e}[/]")
        return

    console.print(f"[green]✓ Paired![/]")
    console.print()

    # --- Step 3: Connect ---
    # First, try to auto-connect. After pairing, adb often knows the device.
    # The connection IP is the SAME as the pairing IP, just a different port.
    # The connection port is shown at the TOP of the Wireless debugging screen.
    console.print("[bold cyan]Step 3: Connect[/]")
    console.print()
    console.print("  [bold]Where to find the connection IP:port:[/]")
    console.print("  Look at the [bold]TOP[/] of the Wireless debugging screen.")
    console.print("  You'll see:")
    console.print("    [green]IP address & port[/]")
    console.print("    [green]192.168.x.x:xxxxx[/]   ← this is the connection address")
    console.print()
    console.print("  [yellow]NOT[/] the 'Paired devices' list below — that shows fingerprints.")
    console.print("  The connection IP:port is at the [bold]very top[/] of the screen,")
    console.print("  right under the 'Wireless debugging' toggle.")
    console.print()
    console.print("  [dim]The IP is the same as the pairing IP, only the port is different.[/]")
    console.print("  [dim]Example: paired with 192.168.1.42:37123 → connect to 192.168.1.42:41234[/]")
    console.print()

    # Try auto-connect first using the pairing IP
    # Extract just the IP from the pairing address
    pair_ip = pair_addr.split(":")[0] if pair_addr else None
    auto_connected = False

    if pair_ip:
        console.print(f"[dim]Trying to auto-connect using pairing IP {pair_ip}...[/]")
        # Try 1: adb connect with just the IP (adb may know the port from pairing)
        try:
            proc = subprocess.run(
                ["adb", "connect", pair_ip],
                capture_output=True, text=True, timeout=10,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            if "connected" in output.lower() and "failed" not in output.lower():
                console.print(f"  [green]✓ Auto-connected![/]")
                console.print(f"  [dim]{output.strip()}[/]")
                auto_connected = True
            else:
                console.print(f"  [dim]Auto-connect didn't work. Will ask for the port.[/]")
        except Exception:
            pass

    if not auto_connected:
        console.print()
        console.print("  [yellow]💡 Tip: Copy the IP:port from the top of the Wireless debugging screen.[/]")
        console.print("     Long-press the IP:port text → Copy, then type 'c' here to paste.")
        console.print()

        conn_addr = prompt_with_clipboard(
            "Enter the connection IP:port (from the TOP of the screen)",
            parse_addr,
            "192.168.1.42:41234"
        )
        if not conn_addr:
            console.print("[red]Aborted.[/]")
            return

        console.print(f"[dim]Connecting to {conn_addr}...[/]")
        try:
            proc = subprocess.run(
                ["adb", "connect", conn_addr],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            console.print(f"  [dim]{output.strip()}[/]")
        except Exception as e:
            console.print(f"[red]✗ Connection error: {e}[/]")
            return

    # --- Verify ---
    console.print()
    console.print("[dim]Verifying connection...[/]")
    try:
        proc = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
        devices_output = proc.stdout.strip()
        console.print(f"  [dim]{devices_output}[/]")
        # Check if any device shows as "device" (not offline/unauthorized)
        lines = devices_output.splitlines()
        connected = False
        for line in lines[1:]:  # skip "List of devices attached"
            if "\tdevice" in line:
                connected = True
                break
        if connected:
            console.print()
            console.print(Panel.fit(
                "[bold green]✓ Self-ADB paired and connected![/]\n\n"
                "[dim]HELIX can now control your phone's UI:[/]\n"
                "  • Take screenshots\n"
                "  • Tap, swipe, type\n"
                "  • Launch and stop apps\n"
                "  • Press hardware keys (back, home, etc.)\n\n"
                "[dim]Try in chat:[/]\n"
                "  [cyan]'take a screenshot'[/]\n"
                "  [cyan]'tap the center of the screen'[/]\n"
                "  [cyan]'open Chrome and go to youtube.com'[/]\n\n"
                "[dim]Note: ADB pairing expires after phone reboot.[/]\n"
                "[dim]Re-run 'helix adb' to re-pair.[/]",
                border_style="green",
            ))
        else:
            console.print("[yellow]⚠ No device shows as 'device' in adb devices.[/]")
            console.print("  Output above shows what adb sees.")
            if "unauthorized" in devices_output:
                console.print("  [dim]Device is unauthorized. Accept the 'Allow USB debugging?' dialog on your phone.[/]")
            elif "offline" in devices_output:
                console.print("  [dim]Device is offline. Try: adb disconnect && adb connect <ip:port>[/]")
            else:
                console.print("  [dim]No device found. Check that Wireless debugging is still ON.[/]")
    except Exception as e:
        console.print(f"[red]✗ Verify error: {e}[/]")


def main():
    cli()


if __name__ == "__main__":
    main()
