"""HELIX ADB setup — self-pairing for phone UI control.

Run with: helix adb
"""
from __future__ import annotations

import re, shutil, subprocess
from rich.console import Console
from rich.panel import Panel

from ..config import HelixConfig

console = Console()


def _parse_addr(s: str) -> str | None:
    """Extract IP:port from arbitrary text (clipboard paste)."""
    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{4,5})', s)
    if m: return m.group(1)
    m = re.search(r'(\[[0-9a-fA-F:]+\]:\d{4,5})', s)
    if m: return m.group(1)
    return None


def _parse_code(s: str) -> str | None:
    """Extract 6-digit code from arbitrary text."""
    m = re.search(r'\b(\d{6})\b', s)
    return m.group(1) if m else None


def _get_clipboard() -> str:
    """Read from Termux clipboard if available."""
    try:
        r = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def _prompt(label: str, parser, example: str) -> str | None:
    """Prompt user, with clipboard paste option (type 'c' to paste)."""
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
            clip = _get_clipboard()
            if clip:
                console.print(f"  [dim]Clipboard:[/]")
                console.print(f"  [cyan]{clip[:200]}[/]")
                parsed = parser(clip)
                if parsed:
                    console.print(f"  [green]✓ Found: {parsed}[/]")
                    return parsed
                console.print("  [yellow]Couldn't parse from clipboard. Type manually:[/]")
                continue
            console.print("  [yellow]Clipboard empty. Install termux-api: pkg install termux-api[/]")
            continue
        parsed = parser(val)
        return parsed if parsed else val


def _check_adb_devices() -> tuple[bool, str]:
    """Check adb devices. Returns (is_connected, raw_output)."""
    try:
        proc = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
        output = proc.stdout.strip()
        lines = output.splitlines()
        for line in lines[1:]:  # skip "List of devices attached"
            line = line.strip()
            if line.endswith("\tdevice"):
                return True, output
        return False, output
    except Exception as e:
        return False, f"Error: {e}"


def run_adb_setup() -> None:
    """Interactive self-ADB pairing. Entry point for `helix adb`."""
    console.print(Panel.fit(
        "[bold]HELIX Self-ADB Setup[/]\n"
        "[dim]Pair your phone to itself for full UI control[/]",
        border_style="blue",
    ))

    config = HelixConfig.load()

    # PC users — different path
    if not config.on_termux:
        console.print("[yellow]⚠ Not running on Termux.[/]")
        console.print("  Self-ADB pairing is for Android phones running HELIX in Termux.")
        console.print("  On PC, install platform-tools and use USB ADB:")
        console.print("    https://developer.android.com/tools/releases/platform-tools")
        return

    # Install adb if missing
    if not shutil.which("adb"):
        console.print("[yellow]⚠ adb not found. Installing android-tools...[/]")
        subprocess.run(["pkg", "install", "-y", "android-tools"])
    if not shutil.which("adb"):
        console.print("[red]✗ Failed to install android-tools. Run: pkg install android-tools[/]")
        return

    console.print("[green]✓ adb is available[/]")
    console.print()

    # Check if already connected
    already_connected, existing = _check_adb_devices()
    if already_connected:
        console.print("[green]✓ Already connected![/]")
        console.print(f"  [dim]{existing}[/]")
        _show_success()
        return

    # --- Step 1: Enable Wireless debugging ---
    console.print("[bold cyan]Step 1: Enable Wireless debugging[/]")
    console.print("  Settings → System → Developer Options → Wireless debugging → ON")
    console.print("  [dim](No Developer Options? Tap 'Build Number' 7x in About Phone)[/]")
    console.print()
    try:
        input("  Press Enter when done...")
    except (EOFError, KeyboardInterrupt):
        return
    console.print()

    # --- Step 2: Pair ---
    console.print("[bold cyan]Step 2: Pair[/]")
    console.print("  In Wireless debugging, tap [bold]'Pair device with pairing code'[/]")
    console.print("  You'll see:")
    console.print("    • IP address & port: [green]192.168.x.x:xxxxx[/]")
    console.print("    • Wi-Fi pairing code: [green]6 digits[/]")
    console.print()
    console.print("  [yellow]💡 Copy each value → type 'c' here to paste.[/]")
    console.print()

    pair_addr = _prompt("Pairing IP:port", _parse_addr, "192.168.1.42:37123")
    if not pair_addr:
        console.print("[red]Aborted.[/]"); return

    # Validate format
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{4,5}$', pair_addr):
        console.print(f"[red]✗ '{pair_addr}' is not a valid IP:port.[/]")
        console.print("  Expected: 192.168.1.42:37123  ·  Tip: type 'c' to paste from clipboard.")
        return

    pair_code = _prompt("6-digit pairing code", _parse_code, "123456")
    if not pair_code:
        console.print("[red]Aborted.[/]"); return

    if not re.match(r'^\d{6}$', pair_code):
        console.print(f"[red]✗ '{pair_code}' is not a valid 6-digit code.[/]")
        return

    console.print()
    console.print(f"[dim]Pairing with {pair_addr}...[/]")

    try:
        proc = subprocess.run(
            ["adb", "pair", pair_addr],
            input=pair_code + "\n",
            capture_output=True, text=True, timeout=30,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        console.print(f"  [dim]{output.strip()}[/]")

        if "Successfully paired" not in output and "successfully" not in output.lower():
            console.print("[red]✗ Pairing failed.[/]")
            console.print("  Common causes:")
            console.print("    • Pairing dialog closed (times out in ~30s)")
            console.print("    • Wrong IP:port or code")
            console.print("    • Different WiFi network")
            return
    except subprocess.TimeoutExpired:
        console.print("[red]✗ Pairing timed out. Dialog may have closed.[/]")
        return
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/]")
        return

    console.print(f"[green]✓ Paired![/]")
    console.print()

    # --- Check if already connected after pairing ---
    # After `adb pair` succeeds, the device is often ALREADY connected.
    # No need for a separate "Step 3" in most cases.
    console.print("[dim]Checking connection...[/]")
    import time
    time.sleep(1)  # give adb a moment
    connected, devices_output = _check_adb_devices()
    console.print(f"  [dim]{devices_output}[/]")

    if connected:
        _show_success()
        return

    # --- Step 3: Manual connect (only if auto-connect didn't work) ---
    console.print()
    console.print("[bold cyan]Step 3: Connect[/]")
    console.print("  Not auto-connected. Find the connection IP:port:")
    console.print("  Look at the [bold]TOP[/] of the Wireless debugging screen")
    console.print("  (NOT the 'Paired devices' list — that shows fingerprints)")
    console.print()
    console.print("  [dim]The IP is the same as pairing IP, only the port is different.[/]")
    console.print()

    conn_addr = _prompt("Connection IP:port", _parse_addr, "192.168.1.42:41234")
    if not conn_addr:
        console.print("[red]Aborted.[/]"); return

    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{4,5}$', conn_addr):
        console.print(f"[red]✗ '{conn_addr}' is not a valid IP:port.[/]")
        return

    console.print(f"[dim]Connecting to {conn_addr}...[/]")
    try:
        proc = subprocess.run(
            ["adb", "connect", conn_addr],
            capture_output=True, text=True, timeout=15,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        console.print(f"  [dim]{output.strip()}[/]")
    except Exception as e:
        console.print(f"[red]✗ Connection error: {e}[/]")
        return

    # --- Final verify ---
    console.print()
    connected, devices_output = _check_adb_devices()
    console.print(f"  [dim]{devices_output}[/]")

    if connected:
        _show_success()
    else:
        console.print()
        console.print("[bold red]✗ Not connected.[/]")
        if "unauthorized" in devices_output:
            console.print("  Accept the 'Allow USB debugging?' dialog on your phone.")
        elif "offline" in devices_output:
            console.print("  Device offline. Try: adb disconnect && adb connect <ip:port>")
        else:
            console.print("  No device found. Manual fix:")
            console.print(f"  [cyan]adb connect <ip:port>[/]  [dim](from top of Wireless debugging screen)[/]")
            console.print(f"  [cyan]adb devices[/]  [dim]to verify[/]")


def _show_success() -> None:
    """Show the success panel."""
    console.print()
    console.print(Panel.fit(
        "[bold green]✓ Self-ADB connected![/]\n\n"
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
