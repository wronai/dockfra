#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
GOAL="${*:-Improve the project}"
python3 -c "
import sys; sys.path.insert(0, '/shared/lib')
import llm_client
print(llm_client.chat(
    'Create a project plan for: $GOAL\nList 3-5 specific tasks with priorities.',
    system_prompt='You are a project planner. Output actionable tasks.'
))
"
