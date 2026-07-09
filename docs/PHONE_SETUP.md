# Phone Setup Guide

This guide walks you through setting up HELIX on Android with **full phone control** — no root required.

## Overview

HELIX gives the agent two layers of phone control:

| Layer | What it does | Requires |
|---|---|---|
| **Termux:API** | Hardware access: SMS, calls, camera, GPS, sensors, torch, notifications, TTS, clipboard, volume, brightness | Termux + Termux:API app + `pkg install termux-api` |
| **ADB UI control** | Tap, swipe, type, screenshot, dump UI tree, launch apps, force-stop apps | + `pkg install android-tools` + self-ADB pairing (Android 11+) |

Both layers work **without root**.

---

## Step 1: Install Termux

**Critical:** Install Termux from [F-Droid](https://f-droid.org/packages/com.termux/), NOT the Play Store. The Play Store version is deprecated and broken.

```bash
# After installing Termux, open it and run:
pkg update -y
pkg install -y python nodejs git curl
```

Also install the **Termux:API** app from F-Droid: https://f-droid.org/packages/com.termux.api/

## Step 2: Install HELIX

```bash
git clone https://github.com/UIoperationParamters29/helix.git
cd helix
bash scripts/install_termux.sh
```

This installs:
- `termux-api` package (CLI for hardware access)
- `android-tools` package (adb command)
- Python dependencies
- Web UI (built via npm)

## Step 3: Grant Termux permissions

Open Android Settings → Apps → Termux → Permissions, and grant:
- **Camera** (for `phone_camera_photo`)
- **Location** (for `phone_location`)
- **Microphone** (for future voice input)
- **Storage** (for file access)
- **Phone** (for `phone_call`)

Also for Termux:API app: grant the same permissions.

For SMS (`phone_sms_send` / `phone_sms_read`): Android Settings → Apps → Termux → Permissions → SMS.

## Step 4: Set your LLM API key

```bash
# Option A: OpenAI
export OPENAI_API_KEY=sk-...

# Option B: Z.ai GLM (recommended if you have access)
export HELIX_PROVIDER=zai
export ZAI_API_KEY=...

# Option C: Local Ollama (no API key, runs offline)
# Install Ollama from https://ollama.com
# In Termux (Ollama doesn't run in Termux directly, but you can point at a PC):
export HELIX_PROVIDER=ollama
export HELIX_BASE_URL=http://192.168.1.100:11434/v1
export HELIX_MODEL=qwen2.5:7b
export HELIX_API_KEY=ollama
```

To persist: add the `export` lines to `~/.bashrc`.

## Step 5: Pair self-ADB (for UI automation)

This is the magic step that lets HELIX tap, swipe, type, and screenshot your phone.

```bash
bash scripts/setup_adb.sh
```

The script walks you through:

1. **Enable Developer Options:** Settings → About Phone → tap "Build Number" 7 times
2. **Enable Wireless debugging:** Settings → Developer Options → Wireless debugging → ON
3. **Pair:** In Wireless debugging, tap "Pair device with pairing code"
   - You'll see an IP:port (like `192.168.1.42:37123`) and a 6-digit code
   - The script runs `adb pair <ip:port>` and prompts for the code
4. **Connect:** Back on the main Wireless debugging screen, note the IP:port under your device name
   - The script runs `adb connect <ip:port>`

After this, HELIX can run `adb shell input tap X Y` etc. to control your phone's UI.

### Why self-ADB is amazing

- No PC required — the phone controls itself
- No root required — ADB permissions are sufficient
- Full UI access — tap, swipe, type, screenshot, launch apps, force-stop apps
- Same ADB you know from PC development, just pointed at localhost

### ADB pairing expires after reboot

If you reboot your phone, you'll need to re-pair. Run `bash scripts/setup_adb.sh` again.

**Alternative: Shizuku** — survives reboots. See https://shizuku.rikka.app/
- Install Shizuku app
- Follow in-app instructions to start Shizuku via wireless ADB (one-time)
- HELIX can then use Shizuku instead of `adb` directly

(Shizuku integration is on the roadmap — for now, raw ADB works.)

## Step 6: Start HELIX

```bash
helix web
```

This starts the FastAPI server on port 8765. Open your phone's browser:

```
http://localhost:8765
```

**Pro tip:** "Add to Home Screen" in your browser menu. This installs HELIX as a PWA — full-screen, no address bar, feels native.

## Step 7: Try it out

In the chat:

- **"Take a screenshot"** — agent calls `phone_ui_screenshot`, returns file path
- **"Tap the center of the screen"** — agent calls `phone_ui_tap 540 960`
- **"Open Chrome and go to example.com"** — agent calls `phone_app_launch` with URL
- **"What's my battery level?"** — agent calls `phone_battery`
- **"Send SMS to +14155551234 saying 'I'll be 10 min late'"** — agent calls `phone_sms_send` (will ask for confirmation by default)
- **"Take a selfie with the front camera"** — agent calls `phone_camera_photo -c 1`
- **"Read me my recent SMS"** — agent calls `phone_sms_read`
- **"What apps are installed?"** — agent calls `phone_app_list`
- **"Set screen brightness to 100"** — agent calls `phone_brightness 100`
- **"Vibrate for 500ms"** — agent calls `phone_vibrate`
- **"Speak 'Hello world' aloud"** — agent calls `phone_tts`

## Troubleshooting

### "termux-api: command not found"

```bash
pkg install termux-api
```

Also make sure the **Termux:API app** (separate APK) is installed from F-Droid.

### "adb: command not found"

```bash
pkg install android-tools
```

### "adb: device unauthorized" or "device offline"

Re-pair:
```bash
adb disconnect
bash scripts/setup_adb.sh
```

### "adb: cannot connect to X.X.X.X:port"

- Make sure phone and Termux are on the same WiFi (they are, since Termux runs on the phone)
- Make sure Wireless debugging is still enabled (it can turn off on reboot)
- Make sure the IP hasn't changed (DHCP can reassign)

### Phone tools return "requires Termux" but you ARE on Termux

The detection checks for `/data/data/com.termux`. If your Termux is installed differently, set:
```bash
export HELIX_ON_TERMUX=1
```

### SMS / call tools fail with permission denied

Go to Android Settings → Apps → Termux → Permissions → grant SMS / Phone.

For Termux:API app: same — grant the relevant permissions.

### Camera tool fails

- Grant Camera permission to both Termux and Termux:API
- Some phones have a hardware camera switch / kill switch — check that

## Security considerations

- **SMS and calls cost money.** By default, `phone_sms_send` and `phone_call` are marked `dangerous: true` and require approval. Don't set `auto_approve_writes: true` unless you trust the agent fully.
- **ADB grants deep system access.** A paired ADB session can install/uninstall apps, read notifications, etc. Only pair your own device.
- **Revoke ADB pairing when not needed.** In Wireless debugging settings, tap "Reset pairing".
- **Review the dangerous_patterns list** in `~/.helix/config.yaml`. Add your own (e.g. blocking `pm uninstall` if paranoid).

## What's next

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how HELIX works internally
- Read [SKILL_DEV.md](SKILL_DEV.md) to write your own skills
- Read [SECURITY.md](SECURITY.md) for the full security model
