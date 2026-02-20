#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
echo "─── Tickets ───"
python3 /shared/lib/ticket_system.py list "$@"
echo ""
