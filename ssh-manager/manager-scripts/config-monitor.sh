#!/bin/bash
echo "─── Monitor LLM Config ───"
ssh ssh-monitor "cat /home/monitor/.service-env 2>/dev/null || echo '(no config yet)'"
echo ""
echo "Enter variable to set (e.g. LLM_MODEL=openai/gpt-4o-mini), or 'q' to quit:"
read -r VARLINE
[ "$VARLINE" = "q" ] || [ -z "$VARLINE" ] && exit 0
KEY=$(echo "$VARLINE" | cut -d= -f1)
ssh ssh-monitor "grep -q '^${KEY}=' /home/monitor/.service-env 2>/dev/null && sed -i 's|^${KEY}=.*|${VARLINE}|' /home/monitor/.service-env || echo '${VARLINE}' >> /home/monitor/.service-env"
echo "✓ Updated ${KEY} on monitor"
