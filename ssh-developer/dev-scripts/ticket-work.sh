#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -z "$1" ] && { echo "Usage: ticket-work <T-XXXX>"; exit 1; }
python3 /shared/lib/ticket_system.py update "$1" --status=in_progress
python3 /shared/lib/ticket_system.py comment "$1" "Started working on this ticket"
echo "✓ $1 marked as in_progress"
