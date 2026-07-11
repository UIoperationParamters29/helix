"""HELIX model switcher — interactive provider + model picker with arrow keys.

Like Hermes's `hermes model` command:
  - Shows current model + provider
  - Lists saved providers (arrow-key navigation)
  - Add new provider (name, base_url, api_key)
  - List models from gateway (arrow-key pick)
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
from .selector import arrow_select, arrow_select_or_type

console = Console()


def _clean_input(val: str) -> str:
    """Aggressively clean input — strip all whitespace, control chars, zero-width."""
    if not val:
        return ""
    # Remove ALL whitespace (including \r, \n, tabs, zero-width spaces)
    import re
    val = re.sub(r'\s+', '', val)
    # Remove zero-width characters
    val = val.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    val = val.replace('\ufeff', '').replace('\u00ad', '')
    return val.strip()


def _input(prompt: str, default: str = "") -> str:
    """Input with default value. Cleans aggressively."""
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return ""


def _input_secret(prompt: str, default: str = "") -> str:
    """Input for sensitive values (API keys). Offers clipboard paste.

    Termux's input() can mangle long pastes. This function:
    1. Offers to paste from clipboard (type 'c')
    2. Cleans the input aggressively (strips all whitespace + hidden chars)
    3. Shows a verification (first 8 + last 4 chars) so user can confirm
    """
    import subprocess

    def get_clipboard() -> str:
        try:
            r = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=3)
            if r.returncode == 0:
                return _clean_input(r.stdout)
        except Exception:
            pass
        return ""

    console.print(f"{prompt}")
    console.print("  [dim]Type it, or press 'c' + Enter to paste from clipboard[/]")

    while True:
        try:
            val = input("  › ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

        if val.lower() in ("c", "clip", "paste"):
            clip = get_clipboard()
            if clip:
                # Show what we got (masked)
                masked = clip[:8] + "..." + clip[-4:] if len(clip) > 12 else clip
                console.print(f"  [dim]Clipboard:[/] [cyan]{masked}[/] ({len(clip)} chars)")
                return clip
            else:
                console.print("  [yellow]Clipboard empty. Install termux-api: pkg install termux-api[/]")
                continue

        if not val:
            if default:
                return default
            continue

        # Clean the typed value
        cleaned = _clean_input(val)
        if cleaned:
            # Show verification for long keys
            if len(cleaned) > 20:
                masked = cleaned[:8] + "..." + cleaned[-4:]
                console.print(f"  [dim]Captured: [cyan]{masked}[/] ({len(cleaned)} chars)[/]")
            return cleaned


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
    """Interactive model/provider switcher with arrow-key navigation."""
    config = HelixConfig.load()

    console.print(Panel.fit(
        "[bold]HELIX Model Switcher[/]\n"
        "[dim]↑↓ to navigate · Enter to select · Ctrl+C to cancel[/]",
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
            for i, p in enumerate(config.saved_providers):
                is_active = (p.get("base_url") == config.base_url and
                            p.get("api_key") == config.api_key)
                marker = " [green]← active[/]" if is_active else ""
                console.print(f"  [cyan]{i+1}.[/] {p.get('name', '?')} — {p.get('model', '?')}{marker}")

        # Main menu — arrow select
        options = [
            "Switch to a saved provider",
            "Add a new provider",
            "Delete a saved provider",
            "List models on current gateway + pick one",
            "Test current model",
            "Set model name manually",
            "Save & exit",
            "Quit without saving",
        ]
        idx = arrow_select(options, "What do you want to do?")
        if idx is None:
            console.print("[dim]Exited.[/]")
            return

        if idx == 0:
            _switch_provider(config)
        elif idx == 1:
            _add_provider(config)
        elif idx == 2:
            _delete_provider(config)
        elif idx == 3:
            _pick_model(config)
        elif idx == 4:
            _test_current(config)
        elif idx == 5:
            _set_model_manually(config)
        elif idx == 6:
            config.save()
            console.print(f"\n[green]✓ Saved to {config.home / 'config.yaml'}[/]")
            console.print(f"  [dim]Active model:[/] [cyan]{config.provider}/{config.model}[/]")
            return
        elif idx == 7:
            console.print("[dim]Exited without saving.[/]")
            return


def _switch_provider(config: HelixConfig) -> None:
    """Switch to a saved provider using arrow keys."""
    if not config.saved_providers:
        console.print("[yellow]No saved providers. Add one first.[/]")
        return

    # Build option labels
    options = []
    for p in config.saved_providers:
        is_active = (p.get("base_url") == config.base_url and
                    p.get("api_key") == config.api_key)
        marker = " ← active" if is_active else ""
        options.append(f"{p.get('name', '?')} — {p.get('model', '?')} ({p.get('base_url', '?')[:40]}){marker}")

    idx = arrow_select(options, "Pick a provider")
    if idx is None:
        return

    p = config.saved_providers[idx]
    config.provider = p.get("provider_type", "openai")
    config.base_url = p.get("base_url")
    config.api_key = p.get("api_key", "")
    config.model = p.get("model", config.model)
    console.print(f"\n[green]✓ Switched to {p.get('name')}[/]")
    console.print(f"  [dim]Model:[/] [cyan]{config.model}[/]")


def _delete_provider(config: HelixConfig) -> None:
    """Delete a saved provider using arrow keys."""
    if not config.saved_providers:
        console.print("[yellow]No saved providers to delete.[/]")
        return

    # Build option labels
    options = []
    for p in config.saved_providers:
        is_active = (p.get("base_url") == config.base_url and
                    p.get("api_key") == config.api_key)
        marker = " ← active" if is_active else ""
        options.append(f"{p.get('name', '?')} — {p.get('model', '?')} ({p.get('base_url', '?')[:40]}){marker}")

    idx = arrow_select(options, "Pick a provider to DELETE")
    if idx is None:
        return

    p = config.saved_providers[idx]
    name = p.get("name", "?")

    # Confirm
    console.print(f"\n[yellow]⚠ Delete '{name}'?[/]")
    confirm_options = ["No, cancel", "Yes, delete it"]
    confirm_idx = arrow_select(confirm_options, "Confirm")
    if confirm_idx != 1:
        console.print("[dim]Cancelled.[/]")
        return

    # Remove from list
    config.saved_providers.pop(idx)
    console.print(f"[green]✓ Deleted '{name}'[/]")

    # If we deleted the active provider, clear the active config
    if p.get("base_url") == config.base_url and p.get("api_key") == config.api_key:
        console.print("[yellow]⚠ Deleted the active provider. Active config cleared.[/]")
        if config.saved_providers:
            console.print("[dim]Switch to another provider to set a new active config.[/]")
        else:
            config.api_key = ""
            config.base_url = None
            console.print("[dim]No providers left. Add one to use HELIX.[/]")


def _add_provider(config: HelixConfig) -> None:
    """Add a new provider."""
    console.print("\n[bold cyan]Add a new provider[/]")

    # Pick provider type using arrow keys
    presets = [
        ("Custom gateway", "openai", "https://your-gateway.com/v1"),
        ("Z.ai (GLM)", "zai", "https://open.bigmodel.cn/api/paas/v4"),
        ("OpenAI", "openai", None),
        ("Ollama (local)", "ollama", "http://localhost:11434/v1"),
        ("LM Studio (local)", "lmstudio", "http://localhost:1234/v1"),
    ]
    preset_options = [f"{name}" for name, _, _ in presets]
    idx = arrow_select(preset_options, "Pick provider type")
    if idx is None:
        return

    name, provider_type, default_url = presets[idx]

    # Custom name for the provider
    custom_name = _input(f"  Name for this provider [{name}]: ", name)
    name = custom_name or name

    # Base URL — clean it (remove trailing whitespace, ensure no \r)
    if default_url:
        base_url = _clean_input(_input(f"  Base URL [{default_url}]: ", default_url))
    else:
        base_url = _clean_input(_input("  Base URL (blank for OpenAI default): "))
        if not base_url:
            base_url = None

    api_key = _input_secret("  API key:")
    if not api_key:
        console.print("[yellow]⚠ No API key. You can add it later.[/]")

    # Fetch models
    if base_url:
        console.print(f"\n  [dim]Fetching models from {base_url}...[/]")
        ok, models, err = _list_models(base_url, api_key)
        if not ok:
            console.print(f"  [red]✗ Failed: {err}[/]")
            console.print("  [dim]Provider saved anyway. Set model manually.[/]")
            models = []
    else:
        console.print("  [dim]No base_url — skipping model fetch.[/]")
        models = []

    selected_model = ""
    if models:
        console.print(f"\n  [green]✓ {len(models)} models available[/]")
        # Use arrow_select_or_type for model picking
        # Show first 30 + "type custom"
        display_models = models[:50]
        selected = arrow_select_or_type(display_models, "Pick a model", allow_custom=True)
        if selected:
            selected_model = selected
        else:
            selected_model = _input("  Model name: ")
    else:
        selected_model = _input("  Model name (e.g. gpt-4o-mini): ")

    # Save
    provider_entry = {
        "name": name,
        "provider_type": provider_type,
        "base_url": base_url,
        "api_key": api_key,
        "model": selected_model,
    }
    config.saved_providers = [p for p in config.saved_providers if p.get("name") != name]
    config.saved_providers.append(provider_entry)

    # Set as active
    config.provider = provider_type
    config.base_url = base_url
    config.api_key = api_key
    config.model = selected_model

    console.print(f"\n[green]✓ Added '{name}' and set as active.[/]")
    console.print(f"  [dim]Model:[/] [cyan]{config.model}[/]")


def _pick_model(config: HelixConfig) -> None:
    """List models on current gateway and pick one with arrow keys."""
    if not config.base_url:
        console.print("[red]No base_url set. Add a provider first.[/]")
        return
    if not config.api_key:
        console.print("[red]No API key set. Add a provider first.[/]")
        return

    console.print(f"\n  [dim]Fetching models from {config.base_url}...[/]")
    ok, models, err = _list_models(config.base_url, config.api_key)
    if not ok:
        console.print(f"  [red]✗ Failed: {err}[/]")
        return

    console.print(f"  [green]✓ {len(models)} models[/]")

    # Find current model index for default selection
    default_idx = 0
    if config.model in models:
        default_idx = models.index(config.model)

    # Show all models with arrow nav (prompt_toolkit handles scrolling)
    # If too many, show first 50 + custom option
    if len(models) > 50:
        display = models[:50]
        console.print(f"  [dim](showing first 50 — type custom for others)[/]")
    else:
        display = models

    selected = arrow_select_or_type(display, "Pick a model", allow_custom=True)
    if selected:
        config.model = selected
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
