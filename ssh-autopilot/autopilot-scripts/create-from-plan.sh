#!/bin/bash
export PYTHONPATH="/shared/lib:$PYTHONPATH"
echo "Enter tickets to create (one per line, format: TITLE | PRIORITY | DESCRIPTION)"
echo "Press Ctrl+D when done:"
while IFS='|' read -r title prio desc; do
    title=$(echo "$title" | xargs)
    prio=$(echo "${prio:-normal}" | xargs)
    desc=$(echo "${desc:-}" | xargs)
    [ -n "$title" ] && python3 /shared/lib/ticket_system.py create "$title" "--priority=$prio" "--desc=$desc"
done
echo "Done."
