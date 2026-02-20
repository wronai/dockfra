"""
Structured JSON logger for dockfra management services.
Writes to /var/log/dockfra/decisions.jsonl (shared Docker volume).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR  = Path(os.environ.get("LOG_DIR", "/var/log/dockfra"))
LOG_FILE = LOG_DIR / "decisions.jsonl"
SERVICE  = os.environ.get("SERVICE_ROLE", os.environ.get("HOSTNAME", "unknown"))


def _write(level: str, message: str, data: dict = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service":   SERVICE,
        "level":     level,
        "message":   message,
    }
    if data:
        entry["data"] = data

    line = json.dumps(entry, ensure_ascii=False)
    print(f"[{level}] {message}", file=sys.stderr)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass  # Never crash the service because of logging


def info(message: str, **data):
    _write("INFO", message, data or None)

def warn(message: str, **data):
    _write("WARN", message, data or None)

def error(message: str, **data):
    _write("ERROR", message, data or None)

def action(message: str, **data):
    """Log a significant decision or action taken by the service."""
    _write("ACTION", message, data or None)

def decision(message: str, reasoning: str = "", **data):
    """Log an LLM-driven or autonomous decision."""
    payload = {"reasoning": reasoning, **data} if reasoning else data
    _write("ACTION", message, payload or None)
