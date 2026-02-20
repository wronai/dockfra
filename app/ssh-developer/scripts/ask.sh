#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
[ -z "$*" ] && { echo "Usage: ask <question>"; exit 1; }
python3 /shared/lib/llm_client.py "$*"
