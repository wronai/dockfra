#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
echo "─── My Tickets (assigned=developer) ───"
python3 /shared/lib/ticket_system.py list --assigned=developer
echo ""
