#!/usr/bin/env bash
# HELIX install script for PC (Linux/macOS/WSL).
#
# Usage:
#   git clone https://github.com/UIoperationParamters29/helix.git
#   cd helix
#   bash scripts/install_pc.sh

set -e

echo "═══════════════════════════════════════════════════════"
echo "  HELIX — PC bootstrap"
echo "═══════════════════════════════════════════════════════"

# Check deps
echo ""
echo "[1/4] Checking dependencies..."
command -v python3 >/dev/null || { echo "✗ python3 not found. Install Python 3.11+."; exit 1; }
command -v node >/dev/null || { echo "✗ node not found. Install Node.js 18+."; exit 1; }
command -v git >/dev/null || { echo "✗ git not found."; exit 1; }
echo "  ✓ python3 $(python3 --version)"
echo "  ✓ node $(node --version)"
echo "  ✓ git $(git --version)"

# Install Python deps
echo ""
echo "[2/4] Installing Python dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Build web UI
echo ""
echo "[3/4] Building web UI..."
cd web
npm install --no-audit --no-fund
npm run build
cd ..

# Init config
echo ""
echo "[4/4] Initializing HELIX_HOME..."
helix setup

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✓ HELIX installed."
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo ""
echo "  1. Set your LLM API key:"
echo "     export OPENAI_API_KEY=sk-..."
echo "     # or for Z.ai GLM:"
echo "     export HELIX_PROVIDER=zai ZAI_API_KEY=..."
echo "     # or for local Ollama:"
echo "     export HELIX_PROVIDER=ollama HELIX_BASE_URL=http://localhost:11434/v1 HELIX_MODEL=qwen2.5:7b"
echo ""
echo "  2. Start the web UI:"
echo "     helix web"
echo "     # then open http://localhost:8765"
echo ""
echo "  3. Or chat in terminal:"
echo "     helix chat"
echo ""
echo "Docs: docs/ARCHITECTURE.md, README.md"
echo ""
