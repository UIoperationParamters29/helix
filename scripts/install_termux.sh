#!/data/data/com.termux/files/usr/bin/env bash
# HELIX bootstrap script for Termux (Android).
#
# Usage:
#   pkg install -y curl git python nodejs
#   curl -fsSL https://raw.githubusercontent.com/UIoperationParamters29/helix/main/scripts/install_termux.sh | bash
#
# Or clone + run locally:
#   git clone https://github.com/UIoperationParamters29/helix.git
#   cd helix && bash scripts/install_termux.sh

set -e

echo "═══════════════════════════════════════════════════════"
echo "  HELIX — Termux bootstrap"
echo "═══════════════════════════════════════════════════════"

# 1. Install system packages
echo ""
echo "[1/6] Installing Termux packages..."
pkg update -y
# rust is needed to build some Python packages from source (jiter, pydantic-core, etc.)
# because Termux's aarch64-android target isn't supported by rustup's prebuilt wheels.
pkg install -y python nodejs git termux-api android-tools rust

# 2. Clone HELIX (if not already in a helix dir)
echo ""
echo "[2/6] Cloning HELIX..."
if [ ! -d "helix" ] && [ ! -f "pyproject.toml" ]; then
  git clone https://github.com/UIoperationParamters29/helix.git
  cd helix
else
  echo "  Already in a helix directory — skipping clone."
fi

# 3. Pick a Python version with the best wheel coverage.
# Python 3.14 (Termux default as of 2026) doesn't have prebuilt wheels for
# many packages on aarch64-android, forcing source builds.
# Python 3.12 / 3.13 have much better coverage.
PY_BIN=python
if command -v python3.12 >/dev/null 2>&1; then
  PY_BIN=python3.12
elif command -v python3.13 >/dev/null 2>&1; then
  PY_BIN=python3.13
fi
echo ""
echo "[3/6] Using Python: $($PY_BIN --version 2>&1)"
echo "  (If installs fail on aarch64, try: pkg install python3.12 && re-run)"

# 4. Create venv + install Python deps
echo ""
echo "[4/6] Installing Python dependencies (core only — no Anthropic/tiktoken)..."
$PY_BIN -m venv .venv
source .venv/bin/activate
# Install core deps only. Anthropic and tiktoken need Rust to build from source
# on Termux; they're optional. Most users on Termux will use OpenAI/Z.ai/Ollama.
pip install --upgrade pip
pip install -e .
# Optional: if you want Anthropic support, uncomment:
# pip install -e ".[anthropic]"

# 5. Build web UI
echo ""
echo "[5/6] Building web UI..."
cd web
npm install --no-audit --no-fund
npm run build
cd ..

# 6. Initialize config
echo ""
echo "[6/6] Initializing HELIX_HOME..."
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
echo "  2. Set your LLM API key:"
echo "     export OPENAI_API_KEY=sk-..."
echo "     # or for Z.ai GLM:"
echo "     export HELIX_PROVIDER=zai ZAI_API_KEY=..."
echo "     # or for local Ollama (no key needed):"
echo "     export HELIX_PROVIDER=ollama HELIX_BASE_URL=http://localhost:11434/v1 HELIX_MODEL=qwen2.5:7b HELIX_API_KEY=ollama"
echo ""
echo "  3. Pair self-ADB for UI control (optional, recommended):"
echo "     bash scripts/setup_adb.sh"
echo ""
echo "  4. Start the web UI:"
echo "     helix web"
echo "     # then open http://localhost:8765 in any browser"
echo "     # or: termux-open-url http://localhost:8765"
echo ""
echo "  5. Or chat in terminal:"
echo "     helix chat"
echo ""
echo "Optional extras (need Rust — already installed above):"
echo "  Anthropic Claude:   pip install -e \".[anthropic]\""
echo "  Token counting:     pip install -e \".[tokens]\""
echo ""
echo "Docs: docs/PHONE_SETUP.md"
echo ""
