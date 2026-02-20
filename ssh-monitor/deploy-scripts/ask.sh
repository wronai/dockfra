#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
python3 /shared/lib/llm_client.py "$*"
