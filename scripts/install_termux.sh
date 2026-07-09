#!/data/data/com.termux/files/usr/bin/env bash
# HELIX bootstrap script for Termux (Android).
#
# Usage:
#   pkg install -y curl git python nodejs
#   curl -fsSL https://raw.githubusercontent.com/<user>/helix/main/scripts/install_termux.sh | bash
#
# Or clone + run locally:
#   git clone https://github.com/<user>/helix && cd helix && bash scripts/install_termux.sh

set -e

echo "═══════════════════════════════════════════════════════"
echo "  HELIX — Termux bootstrap"
echo "═══════════════════════════════════════════════════════"

# 1. Install system packages
echo ""
echo "[1/5] Installing Termux packages..."
pkg update -y
pkg install -y python nodejs git termux-api android-tools

# 2. Clone HELIX (if not already in a helix dir)
echo ""
echo "[2/5] Cloning HELIX..."
if [ ! -d "helix" ] && [ ! -f "pyproject.toml" ]; then
  git clone https://github.com/UIoperationParamters29/helix.git
  cd helix
else
  echo "  Already in a helix directory — skipping clone."
fi

# 3. Install Python deps
echo ""
echo "[3/5] Installing Python dependencies..."
python -m venv .venv
source .venv/bin/activate
pip install -e .

# 4. Build web UI
echo ""
echo "[4/5] Building web UI..."
cd web
npm install --no-audit --no-fund
npm run build
cd ..

# 5. Initialize config
echo ""
echo "[5/5] Initializing HELIX_HOME..."
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
echo "     # or for Z.ai:"
echo "     export HELIX_PROVIDER=zai ZAI_API_KEY=..."
echo ""
echo "  2. Pair self-ADB for UI control (optional, recommended):"
echo "     bash scripts/setup_adb.sh"
echo ""
echo "  3. Start the web UI:"
echo "     helix web"
echo "     # then open http://localhost:8765 in any browser"
echo "     # or use Termux:termux-open-url http://localhost:8765"
echo ""
echo "  4. Or chat in terminal:"
echo "     helix chat"
echo ""
echo "Docs: docs/PHONE_SETUP.md"
echo ""
