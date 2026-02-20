#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
MSG="${*:-}"
[ -z "$MSG" ] && { echo "Usage: ask <question>"; exit 1; }
python3 /shared/lib/llm_client.py "$MSG"
