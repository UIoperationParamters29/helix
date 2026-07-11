"""Interactive arrow-key selector for HELIX CLI.

Uses prompt_toolkit for up/down arrow navigation + Enter to select.
Falls back to numbered input if prompt_toolkit isn't available.
"""
from __future__ import annotations

from typing import Optional


def arrow_select(options: list[str], prompt: str = "Select", default_idx: int = 0) -> Optional[int]:
    """Show a list of options. User navigates with up/down, presses Enter to select.

    Returns the selected index, or None if cancelled.
    Falls back to numbered input if terminal doesn't support raw mode.
    """
    if not options:
        return None

    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
        from prompt_toolkit.styles import Style
        from prompt_toolkit.filters import Condition
        import asyncio

        selected = [default_idx]

        def get_text():
            lines = []
            lines.append(("class:prompt", f"  {prompt} (↑↓ to navigate, Enter to select)\n"))
            for i, opt in enumerate(options):
                if i == selected[0]:
                    lines.append(("class:selected", f"  ▸ {opt}\n"))
                else:
                    lines.append(("class:normal", f"    {opt}\n"))
            return lines

        kb = KeyBindings()

        @kb.add("up")
        def _up(event):
            if selected[0] > 0:
                selected[0] -= 1

        @kb.add("down")
        def _down(event):
            if selected[0] < len(options) - 1:
                selected[0] += 1

        @kb.add("enter")
        def _enter(event):
            event.app.exit(result=selected[0])

        @kb.add("c-c")
        def _cancel(event):
            event.app.exit(result=None)

        style = Style.from_dict({
            "prompt": "#94a3b8 bold",
            "selected": "#3b82f6 bold",
            "normal": "#94a3b8",
        })

        layout = Layout(FormattedTextControl(text=get_text, focusable=True))
        layout.container.window.key_bindings = kb

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=False,
        )

        result = app.run()
        return result

    except Exception:
        # Fallback: numbered input
        print(f"  {prompt}")
        for i, opt in enumerate(options, 1):
            marker = " ◄" if i - 1 == default_idx else ""
            print(f"    {i}. {opt}{marker}")
        try:
            choice = input(f"  Enter number [1-{len(options)}]: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return idx
        except (EOFError, KeyboardInterrupt):
            return None
        return None


def arrow_select_or_type(options: list[str], prompt: str = "Select", allow_custom: bool = True) -> Optional[str]:
    """Like arrow_select but also allows typing a custom value.

    Returns the selected option string, or a custom typed value, or None.
    """
    if not options:
        if allow_custom:
            try:
                val = input(f"  {prompt}: ").strip()
                return val if val else None
            except (EOFError, KeyboardInterrupt):
                return None
        return None

    # Add a "type custom" option at the end
    full_options = list(options)
    if allow_custom:
        full_options.append("✎ Type a custom name...")

    idx = arrow_select(full_options, prompt)
    if idx is None:
        return None
    if allow_custom and idx == len(full_options) - 1:
        # Custom input
        try:
            val = input(f"  Type model name: ").strip()
            return val if val else None
        except (EOFError, KeyboardInterrupt):
            return None
    return options[idx]
