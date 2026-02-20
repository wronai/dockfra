#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
LOGS=$(tail -50 /var/log/monitor-daemon.log 2>/dev/null || echo "No logs")
python3 -c "
import sys; sys.path.insert(0, '/shared/lib')
import llm_client
print(llm_client.chat('Analyze these deployment/monitoring logs and identify any issues:\n\n$LOGS',
    system_prompt='You are a DevOps expert. Identify problems, warnings, and suggest fixes. Be concise.'))
"
