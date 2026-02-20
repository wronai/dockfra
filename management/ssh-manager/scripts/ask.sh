#!/bin/bash
# Shared LLM ask script — used by all SSH roles
[ -z "$*" ] && { echo "Usage: ask <question>"; exit 1; }
export PYTHONPATH="/shared/lib:$PYTHONPATH"
python3 /shared/lib/llm_client.py "$*"
