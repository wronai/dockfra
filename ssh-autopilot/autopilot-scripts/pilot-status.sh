#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
echo "─── Autopilot Status ───"
pgrep -f autopilot-daemon >/dev/null && echo "  Daemon: ✓ Running" || echo "  Daemon: ✗ Stopped"
echo "  Interval: ${AUTOPILOT_INTERVAL:-120}s"
echo "  Enabled: ${AUTOPILOT_ENABLED:-true}"
echo ""
echo "─── Tickets ───"
python3 -c "
import ticket_system as t
print(f'  Open: {len(t.list_tickets(status=\"open\"))}')
print(f'  In progress: {len(t.list_tickets(status=\"in_progress\"))}')
print(f'  Closed: {len(t.list_tickets(status=\"closed\"))}')
" 2>/dev/null
echo ""
echo "─── Recent Log ───"
tail -10 /var/log/autopilot.log 2>/dev/null || echo "  (no log)"
