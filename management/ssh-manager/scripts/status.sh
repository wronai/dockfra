#!/bin/bash
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  PROJECT STATUS — $(date +%H:%M:%S)                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "─── Role Services ───"
for svc in "ssh-developer:2222" "ssh-monitor:2222" "ssh-autopilot:2222"; do
    IFS=':' read -r host port <<< "$svc"
    if timeout 3 bash -c "echo >/dev/tcp/${host}/${port}" 2>/dev/null; then
        printf "  ✓ %-20s reachable\n" "$host"
    else
        printf "  ✗ %-20s unreachable\n" "$host"
    fi
done
echo ""
echo "─── Tickets ───"
export PYTHONPATH="/shared/lib:$PYTHONPATH"
python3 -c "
import ticket_system as ts
o=len(ts.list_tickets(status='open'))
w=len(ts.list_tickets(status='in_progress'))
c=len(ts.list_tickets(status='closed'))
print(f'  Open: {o} | In Progress: {w} | Closed: {c}')
" 2>/dev/null || echo "  (ticket system not available)"
echo ""
