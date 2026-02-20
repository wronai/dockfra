#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -z "$1" ] && { echo "Usage: ticket-done <T-XXXX> [comment]"; exit 1; }
MSG="${2:-Completed}"
python3 /shared/lib/ticket_system.py comment "$1" "$MSG"
python3 /shared/lib/ticket_system.py update "$1" --status=closed
echo "✓ $1 closed"
