"""Text utilities — strip ANSI codes, clean output for LLM context."""
from __future__ import annotations

import re

# ANSI escape sequences: \x1b[...m  (color/style codes)
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
# Rich-style markup that leaked through: [36m, [0m, [1m, [/], etc.
# These appear when tool outputs contain Rich console output that wasn't stripped.
_RICH_LEAK_RE = re.compile(r'\[[\d;]*m|\[/\]|\[bold\]|\[/bold\]|\[dim\]|\[/dim\]|\[cyan\]|\[/cyan\]|\[red\]|\[/red\]|\[green\]|\[/green\]|\[yellow\]|\[/yellow\]|\[blue\]|\[/blue\]|\[magenta\]|\[/magenta\]|\[white\]|\[/white\]')


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences and leaked Rich markup from text.

    This is critical: if the LLM sees color codes in tool outputs, it will
    mimic them in its responses, producing garbage like '[36m 1 [0m'.
    """
    if not text:
        return text
    # Remove ANSI escapes
    text = _ANSI_RE.sub('', text)
    # Remove leaked Rich markup ([36m, [0m, [1m, [/], etc.)
    text = _RICH_LEAK_RE.sub('', text)
    # Remove other common Rich markup patterns like [bold cyan], [/bold cyan]
    text = re.sub(r'\[/?(?:bold|dim|cyan|red|green|yellow|blue|magenta|white|italic|underline|strike)\s*(?:cyan|red|green|yellow|blue|magenta|white)?\]', '', text)
    # Remove [digit] patterns that look like color codes ([36], [0], [1])
    text = re.sub(r'\[(?:\d{1,2})\]', '', text)
    return text


def clean_for_llm(text: str, max_len: int = 50000) -> str:
    """Clean text before sending to LLM: strip ANSI, truncate."""
    text = strip_ansi(text)
    if len(text) > max_len:
        text = text[:max_len//2] + f"\n[...truncated {len(text) - max_len} chars...]\n" + text[-max_len//2:]
    return text
