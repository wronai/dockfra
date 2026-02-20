#!/bin/bash
echo "─── Developer LLM Config ───"
ssh ssh-developer "cat /home/developer/.service-env 2>/dev/null || echo '(no config yet)'"
echo ""
echo "Enter variable to set (e.g. LLM_MODEL=openai/gpt-4o), or 'q' to quit:"
read -r VARLINE
[ "$VARLINE" = "q" ] || [ -z "$VARLINE" ] && exit 0
KEY=$(echo "$VARLINE" | cut -d= -f1)
ssh ssh-developer "grep -q '^${KEY}=' /home/developer/.service-env 2>/dev/null && sed -i 's|^${KEY}=.*|${VARLINE}|' /home/developer/.service-env || echo '${VARLINE}' >> /home/developer/.service-env"
echo "✓ Updated ${KEY} on developer"
