#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
FEATURE="${*:-}"
[ -z "$FEATURE" ] && { echo "Usage: plan <feature description>"; exit 1; }
python3 -c "
import sys; sys.path.insert(0, '/shared/lib')
import llm_client
resp = llm_client.chat(
    'Create a development plan with actionable tickets for: $FEATURE\n\nFormat:\nTICKET: <title>\nPRIORITY: <low|normal|high|critical>\nASSIGN: developer\nDESCRIPTION: <what to do>\n---',
    system_prompt='You are a project manager. Break features into 2-5 specific, actionable tickets.'
)
print(resp)
"
