"""FastAPI + WebSocket server.

Streams events to the web UI in real time.
REST endpoints for session management, file browsing, tool listing.
"""
from __future__ import annotations

import asyncio, json, uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from ...config import HelixConfig
from ...conversation import Conversation
from ...events import Event, MessageEvent, ActionEvent, ObservationEvent, AgentErrorEvent, FinishEvent
from ...memory.manager import load_memory, init_memory_files
from ...skills.loader import load_skill_summaries
from ...tools import all_tools


def create_app(config: HelixConfig | None = None) -> FastAPI:
    cfg = config or HelixConfig.load()
    init_memory_files(cfg.home, cfg.persona)

    app = FastAPI(title="HELIX", version="0.1.0")

    # CORS — allow the dev frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory session registry
    sessions: dict[str, Conversation] = {}

    def get_or_create_session(session_id: str | None = None) -> Conversation:
        if session_id and session_id in sessions:
            return sessions[session_id]
        new_id = session_id or uuid.uuid4().hex[:16]
        conv = Conversation(config=cfg, session_id=new_id)
        conv.load_history()
        sessions[new_id] = conv
        return conv

    # --- REST endpoints ---

    @app.get("/api/health")
    async def health():
        return {"ok": True, "version": "0.1.0", "provider": cfg.provider, "model": cfg.model}

    @app.get("/api/status")
    async def status():
        return {
            "home": str(cfg.home),
            "provider": cfg.provider,
            "model": cfg.model,
            "on_termux": cfg.on_termux,
            "api_key_set": bool(cfg.api_key),
            "base_url": cfg.base_url,
            "persona": cfg.persona,
        }

    @app.get("/api/tools")
    async def list_tools():
        tools = all_tools(cfg)
        return [{
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
            "dangerous": t.dangerous,
            "read_only": t.read_only,
            "tags": t.tags,
        } for t in tools]

    @app.get("/api/skills")
    async def list_skills():
        return load_skill_summaries(cfg.home)

    @app.get("/api/memory")
    async def get_memory():
        return load_memory(cfg.home)

    @app.put("/api/memory/{kind}")
    async def update_memory(kind: str, content: str = Body(..., media_type="text/plain")):
        if kind not in ("IDENTITY", "USER", "MEMORY"):
            raise HTTPException(400, "kind must be IDENTITY, USER, or MEMORY")
        f = cfg.home / f"{kind}.md"
        f.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(f)}

    @app.get("/api/sessions")
    async def list_sessions():
        sd = cfg.home / "sessions"
        out = []
        for f in sorted(sd.glob("*.jsonl")):
            stat = f.stat()
            out.append({
                "id": f.stem,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
        return out

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        f = cfg.home / "sessions" / f"{session_id}.jsonl"
        if not f.exists():
            raise HTTPException(404, "session not found")
        events = []
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                pass
        return {"id": session_id, "events": events}

    @app.post("/api/sessions/new")
    async def new_session():
        conv = get_or_create_session()
        return {"session_id": conv.session_id}

    @app.get("/api/files")
    async def list_files(path: str = "."):
        from ...tools.file import _resolve
        p = _resolve(path, cfg.home)
        if not p.exists():
            raise HTTPException(404, "not found")
        if p.is_file():
            return {"type": "file", "path": str(p), "content": p.read_text(encoding="utf-8", errors="replace")[:50000]}
        items = []
        for f in sorted(p.iterdir()):
            try:
                items.append({
                    "name": f.name,
                    "is_dir": f.is_dir(),
                    "size": f.stat().st_size if f.is_file() else 0,
                    "modified": f.stat().st_mtime,
                })
            except Exception:
                pass
        return {"type": "dir", "path": str(p), "items": items}

    @app.post("/api/test_llm")
    async def test_llm():
        """Make a tiny test request to verify LLM config works.

        Returns the actual URL being hit, status, response, and a hint
        for the most common errors. Use this to debug 'empty response' issues.
        """
        from ...llm import get_llm
        # Reload config from disk + env to pick up latest changes
        fresh_cfg = HelixConfig.load()
        result = {
            "config": {
                "provider": fresh_cfg.provider,
                "model": fresh_cfg.model,
                "base_url": fresh_cfg.base_url,
                "api_key_set": bool(fresh_cfg.api_key),
                "api_key_prefix": (fresh_cfg.api_key[:8] + "...") if fresh_cfg.api_key else None,
            },
        }
        try:
            llm = get_llm(fresh_cfg)
            # Try a minimal completion with NO tools (rules out tool-schema issues)
            resp = await llm.complete(
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                tools=None,
                system="You are a test. Reply with OK.",
            )
            result["ok"] = resp.finish_reason != "error"
            result["finish_reason"] = resp.finish_reason
            result["content"] = resp.content
            result["usage"] = resp.usage
            if resp.finish_reason == "error" and isinstance(resp.raw, dict):
                result["error"] = resp.raw.get("error", "")
                result["status"] = resp.raw.get("status")
                result["url"] = resp.raw.get("url", "")
                result["hint"] = resp.raw.get("hint", "")
            elif hasattr(llm, "client") and hasattr(llm.client, "base_url"):
                result["url"] = f"{llm.client.base_url}chat/completions"
            return result
        except Exception as e:
            result["ok"] = False
            result["error"] = f"{type(e).__name__}: {e}"
            return result

    @app.get("/api/list_models")
    async def list_models():
        """Query the gateway's /v1/models endpoint to see what model names are valid.

        Useful when the user gets 'model not found' errors. Returns the list of
        model IDs the gateway says it supports.
        """
        import httpx
        fresh_cfg = HelixConfig.load()
        if not fresh_cfg.base_url:
            return {"ok": False, "error": "No base_url set. Set HELIX_BASE_URL first."}
        url = fresh_cfg.base_url.rstrip("/") + "/models"
        headers = {"Authorization": f"Bearer {fresh_cfg.api_key}"} if fresh_cfg.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get(url, headers=headers)
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "url": url,
                    "status": r.status_code,
                    "error": r.text[:500],
                }
            data = r.json()
            # OpenAI format: {"data": [{"id": "gpt-4o-mini", ...}, ...]}
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
            return {
                "ok": True,
                "url": url,
                "status": r.status_code,
                "models": sorted(models),
                "count": len(models),
            }
        except Exception as e:
            return {"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"}

    # --- WebSocket: streaming chat ---

    @app.websocket("/ws/chat")
    async def ws_chat(ws: WebSocket):
        await ws.accept()
        conv = None
        try:
            # First message: session setup
            hello = await ws.receive_json()
            session_id = hello.get("session_id")
            conv = get_or_create_session(session_id)
            await ws.send_json({"type": "session_ready", "session_id": conv.session_id})

            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "send":
                    user_text = msg.get("content", "").strip()
                    if not user_text:
                        continue
                    # Run the agent loop and send each event directly to the WebSocket
                    try:
                        async for event in conv.send(user_text):
                            await ws.send_json({
                                "type": event.type,
                                "data": event.model_dump(),
                            })
                        await ws.send_json({"type": "done"})
                    except Exception as e:
                        import traceback
                        await ws.send_json({
                            "type": "error",
                            "message": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(),
                        })
                elif msg.get("type") == "approval":
                    action_id = msg.get("action_id", "")
                    decision = msg.get("decision", "denied")
                    conv.resolve_approval(action_id, decision)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            try:
                await ws.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass

    # --- Static frontend (built Next.js) ---
    web_dist = Path(__file__).parent.parent.parent.parent / "web" / "out"
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="frontend")
    else:
        @app.get("/")
        async def root():
            return JSONResponse({
                "name": "HELIX",
                "version": "0.1.0",
                "note": "Web UI not built. Run: cd web && npm install && npm run build",
                "api_docs": "/docs",
            })

    return app


def run_server(config: HelixConfig | None = None):
    import uvicorn
    cfg = config or HelixConfig.load()

    # Print active config on startup so user can immediately see if it's wrong
    print("\n" + "=" * 60)
    print("  HELIX starting up — active configuration:")
    print("=" * 60)
    print(f"  Provider:  {cfg.provider}")
    print(f"  Model:     {cfg.model}")
    print(f"  Base URL:  {cfg.base_url or '(provider default)'}")
    print(f"  API key:   {'✓ set (' + cfg.api_key[:8] + '...)' if cfg.api_key else '✗ NOT SET'}")
    print(f"  On Termux: {cfg.on_termux}")
    print(f"  Home:      {cfg.home}")
    print(f"  Tools:     {len(__import__('helix.tools', fromlist=['all_tools']).all_tools(cfg))} registered")
    print("=" * 60)

    # Warn about common issues
    if not cfg.api_key:
        print("\n  ⚠ WARNING: No API key set!")
        print("    Set it with: export HELIX_API_KEY=your_key")
    if cfg.base_url and not cfg.base_url.rstrip('/').endswith('/v1') and 'openai.com' not in (cfg.base_url or ''):
        # Check if it might need /v1
        if 'gateway' in (cfg.base_url or '').lower() or 'api.' in (cfg.base_url or '').lower():
            print(f"\n  ⚠ WARNING: Your base_url doesn't end with /v1")
            print(f"    Most gateways need it. Try: export HELIX_BASE_URL={cfg.base_url.rstrip('/')}/v1")
    print(f"\n  Web UI:  http://localhost:{cfg.web_port}")
    print(f"  API docs: http://localhost:{cfg.web_port}/docs")
    print(f"  Test LLM: curl -X POST http://localhost:{cfg.web_port}/api/test_llm\n")

    app = create_app(cfg)
    uvicorn.run(app, host=cfg.web_host, port=cfg.web_port, log_level="info")
