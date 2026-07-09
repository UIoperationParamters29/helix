#!/data/data/com.termux/files/usr/bin/env bash
# HELIX self-ADB pairing helper for Android 11+.
#
# This script walks you through pairing Termux to your own phone via
# wireless ADB, enabling full UI automation (tap/swipe/type/screenshot).
#
# Run inside Termux after install_termux.sh.

set -e

echo "═══════════════════════════════════════════════════════"
echo "  HELIX — Self-ADB pairing"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "This pairs your phone to itself via wireless ADB."
echo "After pairing, HELIX can tap, swipe, type, and take screenshots."
echo ""
echo "Prerequisites:"
echo "  - Android 11 or newer"
echo "  - Developer Options enabled (tap Build Number 7x in Settings → About)"
echo "  - Wireless debugging enabled in Developer Options"
echo ""
read -p "Press Enter when Wireless debugging is ON, or Ctrl+C to abort..."

echo ""
echo "Step 1: Pair your device."
echo "  In Wireless debugging settings, tap 'Pair device with pairing code'."
echo "  You'll see an IP:port (e.g. 192.168.1.42:37123) and a 6-digit code."
echo ""
read -p "Enter the pairing IP:port (e.g. 192.168.1.42:37123): " PAIR_ADDR
read -p "Enter the 6-digit pairing code: " PAIR_CODE

echo ""
echo "Pairing..."
adb pair "$PAIR_ADDR" "$PAIR_CODE" || {
  echo "✗ Pairing failed. Make sure you're on the same WiFi and the pairing screen is still open."
  exit 1
}

echo ""
echo "Step 2: Connect."
echo "  Go back to the main Wireless debugging screen."
echo "  Note the IP:port shown under your device name (different from pairing port)."
echo ""
read -p "Enter the connection IP:port (e.g. 192.168.1.42:41234): " CONN_ADDR

echo ""
echo "Connecting..."
adb connect "$CONN_ADDR" || {
  echo "✗ Connection failed. Try: adb connect $CONN_ADDR"
  exit 1
}

echo ""
echo "Verifying..."
adb devices

# Persist the address for HELIX
echo ""
echo "Saving ADB address to HELIX config..."
echo "export HELIX_ADB_ADDRESS=$CONN_ADDR" >> ~/.bashrc
echo "HELIX_ADB_ADDRESS=$CONN_ADDR" >> ~/.helix/config.yaml 2>/dev/null || true

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✓ Self-ADB paired."
echo "═══════════════════════════════════════════════════════"
echo ""
echo "HELIX can now control your phone's UI. Try in chat:"
echo "  - 'Take a screenshot'"
echo "  - 'Tap the center of the screen'"
echo "  - 'Open Chrome and go to example.com'"
echo "  - 'Type hello world into the focused field'"
echo ""
echo "Note: ADB pairing can expire after phone reboot. Re-run this script to re-pair."
echo ""
echo "For an alternative that survives reboots, install Shizuku:"
echo "  https://shizuku.rikka.app/"
echo ""
