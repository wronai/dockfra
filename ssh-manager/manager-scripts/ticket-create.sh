#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
TITLE="${1:-}"
[ -z "$TITLE" ] && { echo "Usage: ticket-create <title> [--priority=normal] [--desc=...] [--assign=developer]"; exit 1; }
python3 /shared/lib/ticket_system.py create "$@"
