#!/usr/bin/env bash
# HELIX one-line installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/UIoperationParamters29/helix/main/install.sh | bash
#
# Or for Termux (Android):
#   curl -fsSL https://raw.githubusercontent.com/UIoperationParamters29/helix/main/install.sh | bash
#
# The installer detects your platform (Termux / Linux / macOS) and installs
# everything needed: Python, Node.js (only on PC — Termux uses prebuilt UI),
# HELIX itself, and initial config.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}"
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║           HELIX — Agent Harness           ║"
echo "  ║     Self-improving · Phone-native         ║"
echo "  ╚═══════════════════════════════════════════╝"
echo -e "${NC}"

# Detect platform
IS_TERMUX=0
IS_PC=0
if [ -d "/data/data/com.termux" ] || echo "$PREFIX" | grep -q "com.termux"; then
    IS_TERMUX=1
    PLATFORM="Termux (Android)"
elif [ "$(uname)" = "Linux" ] || [ "$(uname)" = "Darwin" ]; then
    IS_PC=1
    PLATFORM="$(uname) ($(uname -m))"
else
    echo -e "${RED}Unsupported platform: $(uname)${NC}"
    echo "HELIX requires Termux (Android), Linux, or macOS."
    exit 1
fi

echo -e "${CYAN}Platform:${NC} $PLATFORM"
echo

# ─── Step 1: Install system dependencies ──────────────────────────────

echo -e "${BLUE}[1/5] Installing system dependencies...${NC}"

if [ "$IS_TERMUX" = "1" ]; then
    pkg update -y >/dev/null 2>&1
    pkg install -y python git termux-api android-tools rust >/dev/null 2>&1
    # termux-api app needed for phone tools
    echo -e "  ${GREEN}✓${NC} Installed: python, git, termux-api, android-tools, rust"
elif [ "$IS_PC" = "1" ]; then
    # Check for python3
    if ! command -v python3 >/dev/null 2>&1; then
        echo -e "  ${YELLOW}⚠${NC} python3 not found. Please install Python 3.11+."
        echo "    Ubuntu/Debian: sudo apt install python3 python3-venv"
        echo "    macOS: brew install python3"
        exit 1
    fi
    # Check for git
    if ! command -v git >/dev/null 2>&1; then
        echo -e "  ${YELLOW}⚠${NC} git not found. Please install git."
        exit 1
    fi
    # Check for node (needed for web UI build)
    if ! command -v node >/dev/null 2>&1; then
        echo -e "  ${YELLOW}⚠${NC} node not found. Install Node.js 18+ to build the web UI."
        echo "    Ubuntu/Debian: sudo apt install nodejs npm"
        echo "    macOS: brew install node"
        echo "    Or: https://nodejs.org/"
        echo -e "  ${YELLOW}Continuing without node — web UI will use prebuilt version.${NC}"
    fi
    echo -e "  ${GREEN}✓${NC} System deps OK"
fi

# ─── Step 2: Clone HELIX ──────────────────────────────────────────────

echo -e "${BLUE}[2/5] Cloning HELIX...${NC}"
if [ -d "helix" ]; then
    echo -e "  ${YELLOW}ℹ${NC} ~/helix already exists — updating..."
    cd helix
    git pull origin main >/dev/null 2>&1 || true
else
    git clone https://github.com/UIoperationParamters29/helix.git >/dev/null 2>&1
    cd helix
fi
echo -e "  ${GREEN}✓${NC} Cloned to $(pwd)"

# ─── Step 3: Python venv + deps ───────────────────────────────────────

echo -e "${BLUE}[3/5] Installing Python dependencies...${NC}"
python3 -m venv .venv 2>/dev/null || python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null 2>&1
pip install -e . >/dev/null 2>&1
echo -e "  ${GREEN}✓${NC} Python deps installed"

# ─── Step 4: Build web UI (PC only — Termux uses prebuilt) ────────────

echo -e "${BLUE}[4/5] Setting up web UI...${NC}"
if [ "$IS_TERMUX" = "1" ]; then
    if [ -d "web/out" ]; then
        echo -e "  ${GREEN}✓${NC} Using prebuilt web UI (web/out/)"
    else
        echo -e "  ${YELLOW}⚠${NC} web/out/ not found. Run: git pull origin main"
    fi
elif [ "$IS_PC" = "1" ] && command -v node >/dev/null 2>&1; then
    echo -e "  ${CYAN}Building web UI (npm install + build)...${NC}"
    cd web
    npm install --no-audit --no-fund >/dev/null 2>&1
    npm run build >/dev/null 2>&1
    cd ..
    echo -e "  ${GREEN}✓${NC} Web UI built"
else
    if [ -d "web/out" ]; then
        echo -e "  ${GREEN}✓${NC} Using prebuilt web UI"
    else
        echo -e "  ${YELLOW}⚠${NC} No node + no prebuilt UI. Web UI won't work."
    fi
fi

# ─── Step 5: Initialize config ────────────────────────────────────────

echo -e "${BLUE}[5/5] Initializing config...${NC}"
helix setup >/dev/null 2>&1 || python -m helix setup >/dev/null 2>&1 || true
echo -e "  ${GREEN}✓${NC} Config initialized at ~/.helix/"

# ─── Done ─────────────────────────────────────────────────────────────

echo
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ HELIX installed successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo
echo -e "${CYAN}Next steps:${NC}"
echo
echo -e "  ${BLUE}1.${NC} Set your LLM API key:"
echo -e "     ${CYAN}export HELIX_API_KEY=your_key${NC}"
echo -e "     ${YELLOW}(most gateways also need:)${NC}"
echo -e "     ${CYAN}export HELIX_BASE_URL=https://your-gateway.com/v1${NC}"
echo -e "     ${CYAN}export HELIX_MODEL=your-model-name${NC}"
echo
if [ "$IS_TERMUX" = "1" ]; then
    echo -e "  ${BLUE}2.${NC} (Optional) Pair self-ADB for phone UI control:"
    echo -e "     ${CYAN}helix adb${NC}"
    echo
    echo -e "  ${BLUE}3.${NC} Start HELIX:"
    echo -e "     ${CYAN}helix tui${NC}  ${YELLOW}(terminal UI — recommended)${NC}"
    echo -e "     ${CYAN}helix web${NC}  ${YELLOW}(web UI at http://localhost:8765)${NC}"
else
    echo -e "  ${BLUE}2.${NC} Start HELIX:"
    echo -e "     ${CYAN}helix web${NC}  ${YELLOW}(web UI at http://localhost:8765)${NC}"
    echo -e "     ${CYAN}helix tui${NC}  ${YELLOW}(terminal UI)${NC}"
fi
echo
echo -e "${YELLOW}To update later:${NC} cd ~/helix && git pull && pip install -e ."
echo
echo -e "${DIM}Docs: https://github.com/UIoperationParamters29/helix${NC}"
