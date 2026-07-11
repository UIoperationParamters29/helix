#!/data/data/com.termux/files/usr/bin/env bash
# HELIX bootstrap script for Termux (Android).
#
# Usage:
#   pkg install -y curl git python
#   curl -fsSL https://raw.githubusercontent.com/UIoperationParamters29/helix/main/scripts/install_termux.sh | bash
#
# Or clone + run locally:
#   git clone https://github.com/UIoperationParamters29/helix.git
#   cd helix && bash scripts/install_termux.sh
#
# NOTE: This script does NOT run `npm install` / `npm run build`.
# Next.js SWC has no prebuilt binary for android-arm64, so building the web UI
# on Termux fails. Instead, the repo ships a prebuilt web/out/ directory
# that FastAPI serves directly. If you change web/ source, rebuild on a PC:
#   cd web && npm install && npm run build
# then commit web/out/.

set -e

echo "═══════════════════════════════════════════════════════"
echo "  HELIX — Termux bootstrap"
echo "═══════════════════════════════════════════════════════"

# 1. Install system packages (NO nodejs needed — web/out/ is prebuilt)
echo ""
echo "[1/4] Installing Termux packages..."
pkg update -y
pkg install -y python git termux-api android-tools rust

# 2. Clone HELIX (if not already in a helix dir)
echo ""
echo "[2/4] Cloning HELIX..."
if [ ! -d "helix" ] && [ ! -f "pyproject.toml" ]; then
  git clone https://github.com/UIoperationParamters29/helix.git
  cd helix
else
  echo "  Already in a helix directory — skipping clone."
fi

# 3. Verify web/out/ exists (prebuilt UI)
echo ""
echo "[3/4] Verifying prebuilt web UI..."
if [ ! -d "web/out" ]; then
  echo "  WARNING: web/out/ not found. The web UI will not be served."
  echo "  Pull the latest main branch: git pull origin main"
fi

# 4. Create venv + install Python deps
echo ""
echo "[4/4] Installing Python dependencies..."
# Pick a Python version with the best wheel coverage.
PY_BIN=python
if command -v python3.12 >/dev/null 2>&1; then
  PY_BIN=python3.12
elif command -v python3.13 >/dev/null 2>&1; then
  PY_BIN=python3.13
fi
echo "  Using Python: $($PY_BIN --version 2>&1)"

$PY_BIN -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# Initialize config
echo ""
echo "Initializing HELIX_HOME..."
helix setup || python -m helix setup || true

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✓ HELIX installed."
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "  1. Activate the venv (or use full paths):"
echo "     source .venv/bin/activate"
echo ""
echo "  2. Set your LLM API key (pick one):"
echo "     # Your gateway:"
echo "     export HELIX_BASE_URL=https://api.gateway.orgn.com"
echo "     export HELIX_API_KEY=YOUR_KEY"
echo "     export HELIX_MODEL=gpt-4o-mini"
echo "     # Z.ai GLM:"
echo "     export HELIX_PROVIDER=zai ZAI_API_KEY=..."
echo "     # Local Ollama:"
echo "     export HELIX_PROVIDER=ollama HELIX_BASE_URL=http://localhost:11434/v1 HELIX_MODEL=qwen2.5:7b HELIX_API_KEY=ollama"
echo ""
echo "  3. (Optional) Pair self-ADB for UI control:"
echo "     bash scripts/setup_adb.sh"
echo ""
echo "  4. Start the web UI:"
echo "     helix web"
echo "     # then open http://localhost:8765 in any browser"
echo "     # or: termux-open-url http://localhost:8765"
echo ""
echo "Optional extras (need Rust — already installed above):"
echo "  Anthropic Claude:   pip install -e \".[anthropic]\""
echo "  Token counting:     pip install -e \".[tokens]\""
echo ""
echo "Docs: docs/PHONE_SETUP.md"
echo ""
