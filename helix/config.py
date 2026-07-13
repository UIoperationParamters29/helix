"""HELIX configuration & profile isolation.

HELIX_HOME (default ~/.helix) is the single root for all per-instance state.
Multiple agents coexist by each owning a different HELIX_HOME.
Nothing in the codebase hard-codes ~/.helix — everything goes through get_helix_home().
"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


def get_helix_home() -> Path:
    """Resolve the HELIX_HOME directory.

    Priority:
      1. HELIX_HOME env var (explicit override)
      2. ~/.helix (default)
    """
    home = os.environ.get("HELIX_HOME")
    if home:
        p = Path(home).expanduser().resolve()
    else:
        p = Path.home() / ".helix"
    p.mkdir(parents=True, exist_ok=True)
    # Standard subdirs
    for sub in ("sessions", "skills", "plugins", "logs", "cache"):
        (p / sub).mkdir(exist_ok=True)
    return p


@dataclass
class HelixConfig:
    """All runtime configuration. Loaded from HELIX_HOME/config.yaml + env."""

    home: Path = field(default_factory=get_helix_home)

    # --- LLM ---
    provider: str = "openai"            # openai | anthropic | zai | ollama | lmstudio | custom
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: Optional[str] = None      # override for OpenAI-compatible endpoints
    max_tokens: int = 8096
    temperature: float = 0.3

    # --- Saved providers (for `helix model` switcher) ---
    # Each entry: {name, base_url, api_key, provider_type}
    # The active provider/model/api_key/base_url above is what's actually used.
    # This list lets you switch between saved providers quickly.
    saved_providers: list[dict] = field(default_factory=list)

    # --- Agent loop ---
    max_iterations: int = 15            # hard cap on tool calls per task (was 30 — too many)
    max_context_tokens: int = 100_000   # condense when exceeded
    stuck_threshold: int = 3            # identical observations -> stuck

    # --- Security ---
    auto_approve_reads: bool = True
    auto_approve_writes: bool = False   # require approval for destructive ops
    dangerous_patterns: list[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/(?!tmp)", r"rm\s+-rf\s+~", r"rm\s+-rf\s+\*",
        r"dd\s+.*of=/dev/", r"mkfs", r"shutdown", r"reboot",
        r":\(\)\{.*\|.*&\};",            # fork bomb
        r"curl.*\|\s*sh", r"wget.*\|\s*sh",
    ])

    # --- Phone (Termux) ---
    on_termux: bool = False             # auto-detected at runtime
    adb_address: Optional[str] = None   # e.g. "192.168.1.42:41234" for self-ADB
    use_shizuku: bool = False

    # --- Web UI ---
    web_host: str = "0.0.0.0"
    web_port: int = 8765

    # --- Persona ---
    persona: str = "HELIX"              # used in system prompt

    # --- Skills ---
    skills_enabled: bool = True
    skill_auto_create: bool = True      # agent may write new skills after tasks

    @classmethod
    def load(cls) -> "HelixConfig":
        """Load config from HELIX_HOME/config.yaml, then env overrides."""
        import yaml
        cfg = cls()
        home = get_helix_home()
        config_file = home / "config.yaml"
        data = {}
        if config_file.exists():
            try:
                data = yaml.safe_load(config_file.read_text()) or {}
            except Exception:
                data = {}
        # Apply file values
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        # Ensure home is a Path (YAML loads it as string)
        if isinstance(cfg.home, str):
            cfg.home = Path(cfg.home).expanduser()
        # Apply env overrides (HELIX_ prefix)
        for k in ("provider", "model", "api_key", "base_url", "max_tokens",
                  "temperature", "max_iterations", "web_host", "web_port",
                  "persona", "adb_address"):
            env_val = os.environ.get(f"HELIX_{k.upper()}")
            if env_val:
                # coerce types
                cur = getattr(cfg, k)
                if isinstance(cur, bool):
                    setattr(cfg, k, env_val.lower() in ("1", "true", "yes", "on"))
                elif isinstance(cur, int):
                    setattr(cfg, k, int(env_val))
                elif isinstance(cur, float):
                    setattr(cfg, k, float(env_val))
                else:
                    setattr(cfg, k, env_val)
        # OpenAI env passthrough
        # If api_key is "***" (from old config saves that masked it), treat as empty
        if not cfg.api_key or cfg.api_key == "***":
            cfg.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not cfg.base_url:
            cfg.base_url = os.environ.get("OPENAI_BASE_URL")
        # Auto-detect Termux
        cfg.on_termux = "com.termux" in os.environ.get("PREFIX", "") or \
                        Path("/data/data/com.termux").exists()
        return cfg

    def save(self) -> None:
        """Persist current config to HELIX_HOME/config.yaml."""
        import yaml
        data = {k: v for k, v in self.__dict__.items()
                if k not in ("home",) and not k.startswith("_")}
        data["home"] = str(self.home)
        # Persist the real API key — this is the user's own machine.
        # The old behavior of writing "***" caused load() to read back "***"
        # as the api_key, which then failed auth.
        # The config file permissions should protect it (chmod 600).
        (self.home / "config.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
        # Set restrictive permissions on config file
        try:
            import os, stat
            os.chmod(self.home / "config.yaml", stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass


def get_config() -> HelixConfig:
    """Convenience accessor."""
    return HelixConfig.load()
