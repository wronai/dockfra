#!/bin/bash
echo "[autopilot] Running manual cycle..."
export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null

# Gather and display status
echo "─── Project State ───"
python3 -c "
import ticket_system as t
for ticket in t.list_tickets():
    print(t.format_ticket(ticket))
" 2>/dev/null
echo ""

# If LLM available, get recommendations
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    echo "─── LLM Analysis ───"
    python3 /shared/lib/llm_client.py "Analyze this project state and suggest next steps. Be brief."
fi
