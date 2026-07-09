"""Phone tool subpackage — Termux:API + self-ADB UI control.

Tools auto-register at import. They gracefully no-op on PC (return helpful
error telling user to install Termux:API or pair ADB).

Two layers:
  1. termux_api_* — phone hardware/sensors via Termux:API CLI
  2. phone_ui_* — full UI automation via self-ADB (tap/swipe/type/screenshot)
"""
# Importing this package auto-loads all phone tools
from . import (sms, call, notification, camera, location, clipboard,
               hardware, tts, ui, apps)  # noqa: F401
