"""Text utilities — strip ANSI codes, clean output for LLM context."""
from __future__ import annotations

import re

# Real ANSI escape sequences: \x1b[36m, \x1b[1;36;40m, etc.
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

# Leaked ANSI codes (escape char stripped but rest remains): [36m, [1m, [0m, [1;36;40m
# These happen when ANSI codes are partially processed — the \x1b is removed
# but [36m stays as literal text. The m is the ANSI terminator (no closing bracket).
_LEAKED_ANSI_RE = re.compile(r'\[\d{1,2}(?:;\d{1,2})*m')

# Rich console markup: [bold], [/bold], [cyan], [/cyan], [bold cyan], [/bold cyan], etc.
# Matches word(s) inside brackets, optionally with / prefix for closing tags
_RICH_MARKUP_RE = re.compile(r'\[/?\w+(?:\s+\w+)*\]')

# Bare numbers in brackets: [1], [36], [0] — leftover fragments
_BARE_NUM_RE = re.compile(r'\[\d{1,2}\]')

# Zero-width and invisible characters
_INVISIBLE_RE = re.compile(r'[\u200b\u200c\u200d\ufeff\u00ad\u200e\u200f]')


def strip_ansi(text: str) -> str:
    """Remove ALL ANSI escape sequences, leaked ANSI codes, and Rich markup from text.

    This is critical: if the LLM sees ANY color codes in tool outputs, it will
    mimic them in its responses, producing garbage like '[36m 1 [0m[1m text [0m'.

    Handles:
    - Real ANSI: \\x1b[36m, \\x1b[1;36;40m
    - Leaked ANSI (no escape char): [36m, [1m, [0m, [1;36;40m
    - Rich markup: [bold], [/bold], [cyan], [bold cyan]
    - Bare fragments: [1], [36], [0]
    - Zero-width chars: \\u200b, \\ufeff, etc.
    """
    if not text:
        return text
    # 1. Remove real ANSI escapes
    text = _ANSI_RE.sub('', text)
    # 2. Remove leaked ANSI codes ([36m, [1m, [0m, [1;36;40m — note: no closing bracket, m is terminator)
    text = _LEAKED_ANSI_RE.sub('', text)
    # 3. Remove Rich markup ([bold], [/bold], [cyan], [bold cyan], etc.)
    text = _RICH_MARKUP_RE.sub('', text)
    # 4. Remove bare number fragments ([1], [36], [0])
    text = _BARE_NUM_RE.sub('', text)
    # 5. Remove zero-width / invisible characters
    text = _INVISIBLE_RE.sub('', text)
    return text


def clean_for_llm(text: str, max_len: int = 50000) -> str:
    """Clean text before sending to LLM: strip ANSI, truncate."""
    text = strip_ansi(text)
    if len(text) > max_len:
        text = text[:max_len//2] + f"\n[...truncated {len(text) - max_len} chars...]\n" + text[-max_len//2:]
    return text
