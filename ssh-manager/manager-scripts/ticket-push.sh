#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -z "$1" ] && { echo "Usage: ticket-push <T-XXXX>"; exit 1; }
python3 /shared/lib/ticket_system.py push "$1"
