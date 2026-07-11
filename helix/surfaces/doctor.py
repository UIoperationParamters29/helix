"""HELIX doctor — diagnose your setup."""
from __future__ import annotations

import asyncio, os
from rich.console import Console
from rich.panel import Panel

from ..config import HelixConfig
from ..tools import all_tools

console = Console()


def run_doctor() -> None:
    """Diagnose HELIX setup: config, env, LLM test, model list."""
    config = HelixConfig.load()

    console.print(Panel.fit(
        "[bold]HELIX Doctor[/] — diagnosing your setup",
        border_style="blue",
    ))

    # 1. Config
    console.print("\n[bold]1. Configuration[/]")
    console.print(f"   Home:        {config.home}")
    config_file = config.home / "config.yaml"
    console.print(f"   Config file: {config_file} [{'✓' if config_file.exists() else '✗ missing'}]")
    console.print(f"   Provider:    {config.provider}")
    console.print(f"   Model:       {config.model}")
    console.print(f"   Base URL:    {config.base_url or '(default)'}")
    console.print(f"   API key:     {'✓ set' if config.api_key else '[red]✗ NOT SET[/]'}")
    console.print(f"   On Termux:   {config.on_termux}")
    console.print(f"   Tools:       {len(all_tools(config))} registered")

    # 2. Env vars
    console.print("\n[bold]2. Environment variables[/]")
    for var in ("HELIX_PROVIDER", "HELIX_MODEL", "HELIX_BASE_URL", "HELIX_API_KEY",
                "OPENAI_API_KEY", "OPENAI_BASE_URL"):
        val = os.environ.get(var)
        if val:
            display = val[:12] + "..." if var.endswith("KEY") and len(val) > 12 else val
            console.print(f"   {var}={display} [green](set)[/]")
        else:
            console.print(f"   {var} [dim](not set)[/]")

    # 3. Issues
    console.print("\n[bold]3. Issues check[/]")
    issues = []
    if not config.api_key:
        issues.append(("red", "No API key", "export HELIX_API_KEY=your_key"))
    if config.base_url and not config.base_url.rstrip('/').endswith('/v1') and 'openai.com' not in (config.base_url or ''):
        if 'gateway' in (config.base_url or '').lower() or 'api.' in (config.base_url or '').lower():
            issues.append(("yellow", "base_url missing /v1 suffix",
                          f"export HELIX_BASE_URL={config.base_url.rstrip('/')}/v1"))
    if not issues:
        console.print("   [green]✓ No obvious issues[/]")
    else:
        for color, msg, fix in issues:
            console.print(f"   [{color}]⚠ {msg}[/]")
            console.print(f"      [dim]Fix:[/] [cyan]{fix}[/]")

    # 4. Test LLM
    if not config.api_key:
        console.print("\n[bold red]Cannot test LLM — no API key set.[/]")
        return

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
                    console.print(f"   [dim]HTTP:[/] {resp.raw['status']}")
                if resp.raw.get("url"):
                    console.print(f"   [dim]URL:[/] {resp.raw['url']}")
                if resp.raw.get("hint"):
                    console.print(f"   [blue]Hint:[/] {resp.raw['hint']}")
        else:
            console.print(f"   [bold green]✓ LLM works![/]  Replied: [cyan]{resp.content}[/]")
    except Exception as e:
        console.print(f"   [bold red]✗ Error:[/] {type(e).__name__}: {e}")

    # 5. List models
    if not config.base_url:
        return

    console.print("\n[bold]5. Models on gateway...[/]")
    import httpx
    url = config.base_url.rstrip("/") + "/models"
    try:
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        r = httpx.get(url, headers=headers, timeout=15)
        if r.status_code >= 400:
            console.print(f"   [red]✗ HTTP {r.status_code}[/]")
            return
        data = r.json()
        models = []
        if isinstance(data, dict) and "data" in data:
            for m in data["data"]:
                if isinstance(m, dict) and "id" in m:
                    models.append(m["id"])
        models.sort()
        console.print(f"   [green]✓ {len(models)} models[/]")
        for m in models[:15]:
            marker = " ← current" if m == config.model else ""
            console.print(f"     [yellow]{m}[/]{marker}")
        if len(models) > 15:
            console.print(f"     [dim]...and {len(models) - 15} more[/]")
        if config.model not in models:
            console.print(f"\n   [bold red]⚠ Your model '{config.model}' is NOT in the list![/]")
            console.print(f"   [cyan]export HELIX_MODEL=<one_from_above>[/]")
    except Exception as e:
        console.print(f"   [red]✗ Error: {e}[/]")

    console.print("\n[bold]Done.[/]")
