#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -z "$1" ] && { echo "Usage: ticket-show <T-XXXX>"; exit 1; }
python3 /shared/lib/ticket_system.py show "$1"
