#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
TICKET_ID="${1:-}"
[ -z "$TICKET_ID" ] && { echo "Usage: implement <T-XXXX>"; exit 1; }
python3 -c "
import sys, json; sys.path.insert(0, '/shared/lib')
import ticket_system, llm_client
t = ticket_system.get('$TICKET_ID')
if not t: print('Ticket not found'); sys.exit(1)
print(f'Ticket: {t[\"title\"]}')
print(f'Description: {t.get(\"description\", \"\")}')
print()
resp = llm_client.chat(
    f'Implement this ticket:\nTitle: {t[\"title\"]}\nDescription: {t.get(\"description\", \"\")}\n\nProvide the code implementation.',
    system_prompt='You are a developer. Write clean, tested code. Include file paths and any necessary changes.'
)
print(resp)
ticket_system.add_comment('$TICKET_ID', 'developer', 'AI-assisted implementation generated')
ticket_system.update('$TICKET_ID', status='in_progress')
"
