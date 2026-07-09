"""Web tools — fetch URLs + search the web.

Uses httpx directly so it works in Termux without extra deps.
Search uses DuckDuckGo HTML (no API key needed) by default;
Z.ai SDK if ZAI_API_KEY is present.
"""
from __future__ import annotations

import os, re, html
from typing import Any
from urllib.parse import quote_plus, urljoin

from .base import Tool, ToolResult, tool


@tool
class WebFetch(Tool):
    name = "web_fetch"
    description = (
        "Fetch a URL and return cleaned text content. "
        "Strips scripts/styles/nav. Good for reading articles, docs, APIs. "
        "Returns first 20k chars by default."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "default": 20000},
            "raw": {"type": "boolean", "default": False, "description": "Return raw HTML."},
        },
        "required": ["url"],
    }
    read_only = True
    tags = ["web"]

    async def run(self, url: str, max_chars: int = 20000, raw: bool = False) -> ToolResult:
        import httpx
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=20) as c:
                r = await c.get(url, headers={"User-Agent": "HELIX-Agent/0.1 (+https://github.com/helix-agent)"})
                if r.status_code >= 400:
                    return ToolResult.err(f"HTTP {r.status_code}: {r.reason_phrase}",
                                          status=r.status_code)
                content_type = r.headers.get("content-type", "")
                text = r.text
                if raw or "html" not in content_type:
                    return ToolResult.ok(text[:max_chars], url=url, status=r.status_code)
                # Clean HTML
                text = _clean_html(text)
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n\n[...truncated {len(text)-max_chars} chars...]"
                return ToolResult.ok(text, url=url, status=r.status_code, content_type=content_type)
        except Exception as e:
            return ToolResult.err(f"Fetch failed: {e}")


@tool
class WebSearch(Tool):
    name = "web_search"
    description = (
        "Search the web. Returns titles, URLs, and snippets for top results. "
        "Uses Z.ai search if ZAI_API_KEY set, else DuckDuckGo HTML."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "num": {"type": "integer", "default": 8},
        },
        "required": ["query"],
    }
    read_only = True
    tags = ["web", "search"]

    async def run(self, query: str, num: int = 8) -> ToolResult:
        # Try Z.ai first
        zai_key = os.environ.get("ZAI_API_KEY") or self.config.api_key if self.config.provider == "zai" else os.environ.get("ZAI_API_KEY")
        if zai_key:
            try:
                results = await self._zai_search(query, num)
                if results:
                    return ToolResult.ok(self._format(results), query=query, source="zai", count=len(results))
            except Exception:
                pass  # fall through to DuckDuckGo
        # Fallback: DuckDuckGo HTML
        try:
            results = await self._ddg_search(query, num)
            return ToolResult.ok(self._format(results), query=query, source="duckduckgo", count=len(results))
        except Exception as e:
            return ToolResult.err(f"Search failed: {e}")

    async def _zai_search(self, query: str, num: int) -> list[dict]:
        # Use z-ai-web-dev-sdk CLI if available, else skip
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "z-ai", "function", "-n", "web_search",
            "-a", f'{{"query": "{query}", "num": {num}}}',
            "-o", "/tmp/_helix_search.json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            raise RuntimeError("z-ai CLI failed")
        import json
        try:
            data = json.load(open("/tmp/_helix_search.json"))
            results = data if isinstance(data, list) else data.get("results", [])
            return [{"title": r.get("name", ""), "url": r.get("url", ""),
                     "snippet": r.get("snippet", "")} for r in results[:num]]
        except Exception:
            return []

    async def _ddg_search(self, query: str, num: int) -> list[dict]:
        import httpx
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as c:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            text = r.text
        results = []
        # Parse DuckDuckGo HTML result blocks
        for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.+?)</a>.*?<a[^>]+class="result__snippet"[^>]*>(.+?)</a>', text, re.S):
            url = m.group(1)
            # DDG wraps URLs in a redirect
            url = re.sub(r'^//duckduckgo.com/l/\?uddg=', '', url)
            from urllib.parse import unquote, parse_qs, urlparse
            try:
                parsed = urlparse(url)
                if 'uddg' in parse_qs(parsed.query):
                    url = parse_qs(parsed.query)['uddg'][0]
            except Exception:
                pass
            title = _strip_tags(m.group(2))
            snippet = _strip_tags(m.group(3))
            results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= num:
                break
        return results

    def _format(self, results: list[dict]) -> str:
        if not results:
            return "(no results)"
        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title','(no title)')}")
            lines.append(f"   {r.get('url','')}")
            lines.append(f"   {r.get('snippet','')[:200]}")
            lines.append("")
        return "\n".join(lines)


def _clean_html(html_text: str) -> str:
    html_text = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', html_text, flags=re.I)
    html_text = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', html_text, flags=re.I)
    html_text = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', ' ', html_text, flags=re.I)
    html_text = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', ' ', html_text, flags=re.I)
    html_text = re.sub(r'<header[^>]*>[\s\S]*?</header>', ' ', html_text, flags=re.I)
    html_text = re.sub(r'<br\s*/?>', '\n', html_text, flags=re.I)
    html_text = re.sub(r'</p>', '\n\n', html_text, flags=re.I)
    html_text = re.sub(r'<[^>]+>', '', html_text)
    html_text = html.unescape(html_text)
    html_text = re.sub(r'\n{3,}', '\n\n', html_text)
    html_text = re.sub(r'[ \t]+', ' ', html_text)
    return html_text.strip()


def _strip_tags(s: str) -> str:
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s).strip()
