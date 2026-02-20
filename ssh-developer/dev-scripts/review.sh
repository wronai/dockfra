#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
FILE="${1:-}"
[ -z "$FILE" ] && { echo "Usage: review <file>"; exit 1; }
[ ! -f "$FILE" ] && [ -f "/repo/$FILE" ] && FILE="/repo/$FILE"
[ ! -f "$FILE" ] && { echo "File not found: $FILE"; exit 1; }
CONTENT=$(cat "$FILE")
python3 -c "
import sys; sys.path.insert(0, '/shared/lib')
import llm_client
code = open('$FILE').read()
print(llm_client.chat(
    f'Review this code and suggest improvements:\n\n\`\`\`\n{code}\n\`\`\`',
    system_prompt='You are a senior code reviewer. Be concise. Focus on bugs, security, and best practices.'
))
"
