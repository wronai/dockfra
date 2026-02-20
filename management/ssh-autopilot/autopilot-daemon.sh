#!/bin/bash
# autopilot-daemon.sh — Autonomous orchestration via LLM
set -uo pipefail

export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null

CYCLE=0
log() { echo "$(date -Iseconds) [autopilot] $*"; }

gather_status() {
    # Collect project state for LLM decision-making
    local tickets_open tickets_wip
    tickets_open=$(python3 -c "import ticket_system as t; ts=t.list_tickets(status='open'); [print(f'  {x[\"id\"]}: {x[\"title\"]} (prio={x[\"priority\"]}, assign={x[\"assigned_to\"]})') for x in ts]" 2>/dev/null || echo "(unavailable)")
    tickets_wip=$(python3 -c "import ticket_system as t; ts=t.list_tickets(status='in_progress'); [print(f'  {x[\"id\"]}: {x[\"title\"]}') for x in ts]" 2>/dev/null || echo "(none)")

    # Service health
    local health=""
    for s in "frontend:80" "backend:${BACKEND_PORT:-8081}" "mobile-backend:${MOBILE_BACKEND_PORT:-8082}"; do
        IFS=':' read -r n p <<< "$s"
        curl -sf "http://$n:$p/health" >/dev/null 2>&1 && health="${health}$n: UP\n" || health="${health}$n: DOWN\n"
    done

    # Developer status via SSH
    local dev_status
    dev_status=$(ssh ssh-developer "cd /repo 2>/dev/null && git log --oneline -3 2>/dev/null || echo 'no repo'" 2>/dev/null || echo "unreachable")

    echo "OPEN TICKETS:
$tickets_open

IN PROGRESS:
$tickets_wip

SERVICE HEALTH:
$(echo -e "$health")
RECENT DEV COMMITS:
$dev_status"
}

run_cycle() {
    log "=== Autopilot cycle $CYCLE ==="

    if [ -z "${OPENROUTER_API_KEY:-}" ]; then
        log "No API key — running basic checks only"
        # Basic: check for stale tickets
        python3 -c "
import ticket_system as t
open_tickets = t.list_tickets(status='open')
if not open_tickets:
    print('No open tickets.')
else:
    print(f'{len(open_tickets)} open ticket(s) awaiting work.')
" 2>/dev/null
        return
    fi

    STATUS=$(gather_status)
    log "Status gathered, consulting LLM..."

    DECISION=$(python3 -c "
import sys; sys.path.insert(0, '/shared/lib')
import llm_client
status = '''$STATUS'''
resp = llm_client.chat(
    f'Given this project status, what actions should be taken?\n\n{status}\n\nRespond with a brief action list (max 3 actions). Each action: ACTION: <description>',
    system_prompt='You are an autonomous DevOps orchestrator. Analyze status and suggest concrete actions. Be concise.'
)
print(resp)
" 2>/dev/null)

    log "LLM decisions:"
    echo "$DECISION" | while read -r line; do
        [ -n "$line" ] && log "  $line"
    done
}

log "Autopilot daemon starting (interval=${AUTOPILOT_INTERVAL:-120}s, enabled=${AUTOPILOT_ENABLED:-true})"
sleep 30

while true; do
    CYCLE=$((CYCLE + 1))

    if [ "${AUTOPILOT_ENABLED}" = "true" ]; then
        run_cycle 2>&1 || log "Cycle error (continuing)"
    fi

    sleep "${AUTOPILOT_INTERVAL:-120}"
done
