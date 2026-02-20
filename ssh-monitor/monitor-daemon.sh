#!/bin/bash
# monitor-daemon.sh — Polls git for changes, monitors health, uses LLM for analysis
set -uo pipefail

export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null

REPO="/repo"
LAST_FILE="$HOME/.last-deployed-commit"
CYCLE=0

log() { echo "$(date -Iseconds) [monitor] $*"; }

get_head() { [ -d "$REPO/.git" ] && (cd "$REPO" && git rev-parse HEAD 2>/dev/null) || echo "none"; }
get_last() { cat "$LAST_FILE" 2>/dev/null || echo "none"; }
save_last() { echo "$1" > "$LAST_FILE"; }

log "Monitor daemon starting (poll=${MONITOR_POLL_INTERVAL:-60}s, auto=${MONITOR_AUTO_DEPLOY:-true})"
sleep 15

while true; do
    CYCLE=$((CYCLE + 1))
    current=$(get_head); last=$(get_last)

    if [ "$current" != "$last" ] && [ "$current" != "none" ]; then
        log "New commit: ${last:0:8} → ${current:0:8}"
        if [ "${MONITOR_AUTO_DEPLOY}" = "true" ]; then
            log "Auto-deploying..."
            "$HOME/deploy/deploy-all.sh" 2>&1 && { log "✓ Deploy OK"; save_last "$current"; } || log "✗ Deploy failed"
        else
            log "Auto-deploy disabled"; save_last "$current"
        fi
    fi

    # Health check every 5 cycles
    if [ $((CYCLE % 5)) -eq 0 ]; then
        log "--- Health (cycle $CYCLE) ---"
        for s in "frontend:80" "backend:${BACKEND_PORT:-8081}" "mobile-backend:${MOBILE_BACKEND_PORT:-8082}"; do
            IFS=':' read -r n p <<< "$s"
            curl -sf "http://$n:$p/health" >/dev/null 2>&1 || log "⚠ $n DOWN"
        done
    fi

    # Check tickets every 10 cycles
    if [ $((CYCLE % 10)) -eq 0 ]; then
        OPEN=$(python3 -c "import ticket_system as t; print(len(t.list_tickets(status='open')))" 2>/dev/null || echo "?")
        log "Tickets open: $OPEN"
    fi

    sleep "${MONITOR_POLL_INTERVAL:-60}"
done
