#!/usr/bin/env python3
"""
Desktop Application — Simulates a Tauri-like desktop app.
In production, this would be a Rust/Tauri application.
For the Docker environment, we use a Python GUI for testing.
"""
import os
import sys
import json
import urllib.request
from datetime import datetime

APP_NAME = os.environ.get("APP_NAME", "InfraDemo")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8081")
DEPLOY_MODE = os.environ.get("DEPLOY_MODE", "local")


def check_backend():
    """Check backend connectivity."""
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    """Main desktop application entry point."""
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  {APP_NAME} Desktop v{APP_VERSION:<20} ║")
    print(f"║  Mode: {DEPLOY_MODE:<33} ║")
    print(f"╚══════════════════════════════════════════╝")
    print()

    # Check backend
    print("[*] Checking backend connectivity...")
    status = check_backend()
    if status.get("status") == "ok":
        print(f"[✓] Backend: OK (v{status.get('version', '?')})")
    else:
        print(f"[✗] Backend: {status.get('error', 'unreachable')}")

    # Device registration
    try:
        import platform
        device_info = {
            "device_id": f"desktop-{platform.node()}",
            "device_type": "desktop",
            "os": platform.system(),
            "arch": platform.machine(),
            "app_version": APP_VERSION
        }
        print(f"[*] Device: {device_info['os']} {device_info['arch']}")
    except Exception as e:
        print(f"[!] Device info error: {e}")

    print(f"\n[*] Desktop app started at {datetime.utcnow().isoformat()}")
    print("[*] Ready for interaction (headless mode)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
