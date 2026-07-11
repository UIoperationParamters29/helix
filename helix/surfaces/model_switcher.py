"""HELIX model switcher — interactive provider + model picker.

Like Hermes's `hermes model` command:
  - Shows current model + provider
  - Lists saved providers
  - Add new provider (name, base_url, api_key)
  - List models from gateway
  - Select model → saves to config

Run with: helix model
"""
from __future__ import annotations

import asyncio, json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from ..config import HelixConfig

console = Console()


def _input(prompt: str, default: str = "") -> str:
    """Input with default value."""
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return ""


def _list_models(base_url: str, api_key: str) -> tuple[bool, list[str], str]:
    """Fetch models from gateway. Returns (ok, models, error)."""
    import httpx
    url = base_url.rstrip("/") + "/models"
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        r = httpx.get(url, headers=headers, timeout=15)
        if r.status_code >= 400:
            return False, [], f"HTTP {r.status_code}: {r.text[:200]}"
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
        return True, models, ""
    except Exception as e:
        return False, [], f"{type(e).__name__}: {e}"


def _test_model(base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """Test a model with a tiny request."""
    import httpx
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        r = httpx.post(url, headers=headers, json={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 50,
        }, timeout=30)
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}: {r.text[:300]}"
        data = r.json()
        if "choices" in data and data["choices"]:
            content = data["choices"][0].get("message", {}).get("content", "") or "(empty)"
            return True, content
        elif "error" in data:
            return False, str(data["error"])[:300]
        return False, f"No choices in response: {str(data)[:200]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run_model_switcher() -> None:
    """Interactive model/provider switcher."""
    config = HelixConfig.load()

    console.print(Panel.fit(
        "[bold]HELIX Model Switcher[/]\n"
        "[dim]Switch providers, add API keys, pick models[/]",
        border_style="blue",
    ))

    while True:
        # Show current config
        console.print("\n[bold]Current configuration:[/]")
        console.print(f"  [dim]Provider:[/] [cyan]{config.provider}[/]")
        console.print(f"  [dim]Model:[/]    [cyan]{config.model}[/]")
        console.print(f"  [dim]Base URL:[/] {config.base_url or '(provider default)'}")
        console.print(f"  [dim]API key:[/]  {'✓ set' if config.api_key else '[red]✗ NOT SET[/]'}")

        # Show saved providers
        if config.saved_providers:
            console.print(f"\n[bold]Saved providers ({len(config.saved_providers)}):[/]")
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("idx", style="dim", width=4)
            table.add_column("name", style="cyan")
            table.add_column("base_url", style="dim")
            table.add_column("model", style="green")
            for i, p in enumerate(config.saved_providers, 1):
                is_active = (p.get("base_url") == config.base_url and
                            p.get("api_key") == config.api_key)
                marker = " [green]← active[/]" if is_active else ""
                table.add_row(
                    f"{i}.",
                    p.get("name", "?"),
                    (p.get("base_url") or "(default)")[:50],
                    p.get("model", "?") + marker,
                )
            console.print(table)

        # Menu
        console.print("\n[bold]Options:[/]")
        console.print("  [cyan]1[/] Switch to a saved provider")
        console.print("  [cyan]2[/] Add a new provider")
        console.print("  [cyan]3[/] List models on current gateway + pick one")
        console.print("  [cyan]4[/] Test current model")
        console.print("  [cyan]5[/] Set model name manually")
        console.print("  [cyan]6[/] Save & exit")
        console.print("  [cyan]q[/] Quit without saving")
        console.print()

        choice = _input("Choice [1-6/q]: ").lower()

        if choice == "q":
            console.print("[dim]Exited without saving.[/]")
            return
        elif choice == "1":
            _switch_provider(config)
        elif choice == "2":
            _add_provider(config)
        elif choice == "3":
            _pick_model(config)
        elif choice == "4":
            _test_current(config)
        elif choice == "5":
            _set_model_manually(config)
        elif choice == "6":
            config.save()
            console.print(f"\n[green]✓ Saved to {config.home / 'config.yaml'}[/]")
            console.print(f"  [dim]Active model:[/] [cyan]{config.provider}/{config.model}[/]")
            console.print(f"  [dim]Restart HELIX for changes to take effect.[/]")
            return
        else:
            console.print("[red]Invalid choice.[/]")


def _switch_provider(config: HelixConfig) -> None:
    """Switch to a saved provider."""
    if not config.saved_providers:
        console.print("[yellow]No saved providers. Add one first (option 2).[/]")
        return
    try:
        idx = int(_input(f"Provider number [1-{len(config.saved_providers)}]: "))
        if idx < 1 or idx > len(config.saved_providers):
            console.print("[red]Invalid number.[/]")
            return
    except ValueError:
        console.print("[red]Invalid number.[/]")
        return

    p = config.saved_providers[idx - 1]
    config.provider = p.get("provider_type", "openai")
    config.base_url = p.get("base_url")
    config.api_key = p.get("api_key", "")
    config.model = p.get("model", config.model)
    console.print(f"[green]✓ Switched to {p.get('name')}[/]")
    console.print(f"  [dim]Model:[/] [cyan]{config.model}[/]")


def _add_provider(config: HelixConfig) -> None:
    """Add a new provider."""
    console.print("\n[bold cyan]Add a new provider[/]")
    console.print("  [dim]Common presets: zai, openai, ollama, lmstudio[/]")
    console.print("  [dim]Or type a custom name.[/]")
    console.print()

    name = _input("  Provider name (e.g. 'my-gateway'): ")
    if not name:
        console.print("[red]Name required.[/]")
        return

    # Preset URLs
    presets = {
        "zai": ("https://open.bigmodel.cn/api/paas/v4", "zai"),
        "openai": (None, "openai"),
        "ollama": ("http://localhost:11434/v1", "ollama"),
        "lmstudio": ("http://localhost:1234/v1", "lmstudio"),
    }
    if name.lower() in presets:
        default_url, provider_type = presets[name.lower()]
        base_url = _input(f"  Base URL [{default_url or '(OpenAI default)'}]: ", default_url or "")
        config.provider = provider_type
    else:
        default_url = "https://your-gateway.com/v1"
        base_url = _input(f"  Base URL [{default_url}]: ", default_url)
        config.provider = "openai"  # most gateways are OpenAI-compatible

    api_key = _input("  API key (paste here): ")
    if not api_key:
        console.print("[yellow]⚠ No API key set. You can add it later.[/]")

    console.print(f"\n  [dim]Fetching models from {base_url or '(default)'}...[/]")
    ok, models, err = _list_models(base_url, api_key)
    if not ok:
        console.print(f"  [red]✗ Failed to list models: {err}[/]")
        console.print("  [dim]Provider saved anyway. You can set model manually.[/]")
        models = []

    selected_model = ""
    if models:
        console.print(f"\n  [green]✓ {len(models)} models available[/]")
        # Show first 20
        for i, m in enumerate(models[:20], 1):
            console.print(f"    [cyan]{i:2}.[/] [yellow]{m}[/]")
        if len(models) > 20:
            console.print(f"    [dim]...and {len(models) - 20} more[/]")

        console.print()
        model_choice = _input(f"  Pick model number [1-{min(len(models), 20)}] or type name: ")
        if model_choice.isdigit():
            idx = int(model_choice)
            if 1 <= idx <= min(len(models), 20):
                selected_model = models[idx - 1]
        if not selected_model and model_choice:
            selected_model = model_choice
        if not selected_model and models:
            selected_model = models[0]
            console.print(f"  [dim]Defaulting to first model: {selected_model}[/]")

    if not selected_model:
        selected_model = _input("  Model name (e.g. gpt-4o-mini): ")

    # Save to saved_providers list
    provider_entry = {
        "name": name,
        "provider_type": config.provider,
        "base_url": base_url or None,
        "api_key": api_key,
        "model": selected_model,
    }
    # Remove existing entry with same name
    config.saved_providers = [p for p in config.saved_providers if p.get("name") != name]
    config.saved_providers.append(provider_entry)

    # Set as active
    config.base_url = base_url or None
    config.api_key = api_key
    config.model = selected_model

    console.print(f"\n[green]✓ Added provider '{name}' and set as active.[/]")
    console.print(f"  [dim]Model:[/] [cyan]{config.model}[/]")


def _pick_model(config: HelixConfig) -> None:
    """List models on current gateway and pick one."""
    if not config.base_url:
        console.print("[red]No base_url set. Add a provider first (option 2).[/]")
        return
    if not config.api_key:
        console.print("[red]No API key set. Add a provider first (option 2).[/]")
        return

    console.print(f"\n  [dim]Fetching models from {config.base_url}...[/]")
    ok, models, err = _list_models(config.base_url, config.api_key)
    if not ok:
        console.print(f"  [red]✗ Failed: {err}[/]")
        return

    console.print(f"  [green]✓ {len(models)} models[/]")
    # Show with current model marked
    for i, m in enumerate(models[:30], 1):
        marker = " [green]← current[/]" if m == config.model else ""
        console.print(f"    [cyan]{i:2}.[/] [yellow]{m}[/]{marker}")
    if len(models) > 30:
        console.print(f"    [dim]...and {len(models) - 30} more (type name to filter)[/]")

    console.print()
    choice = _input(f"  Pick number [1-{min(len(models), 30)}] or type model name: ")
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= min(len(models), 30):
            config.model = models[idx - 1]
            console.print(f"\n[green]✓ Model set to: {config.model}[/]")
            return
    if choice:
        config.model = choice
        console.print(f"\n[green]✓ Model set to: {config.model}[/]")
    else:
        console.print("[dim]No change.[/]")


def _test_current(config: HelixConfig) -> None:
    """Test the current model."""
    if not config.api_key:
        console.print("[red]No API key set.[/]")
        return
    console.print(f"\n  [dim]Testing {config.model}...[/]")
    ok, result = _test_model(config.base_url or "https://api.openai.com/v1", config.api_key, config.model)
    if ok:
        console.print(f"  [green]✓ Works![/] Replied: [cyan]{result}[/]")
    else:
        console.print(f"  [red]✗ Failed:[/]")
        console.print(f"  [red]{result}[/]")


def _set_model_manually(config: HelixConfig) -> None:
    """Set model name manually."""
    console.print(f"\n  [dim]Current model: {config.model}[/]")
    new_model = _input("  New model name: ")
    if new_model:
        config.model = new_model
        console.print(f"[green]✓ Model set to: {config.model}[/]")
