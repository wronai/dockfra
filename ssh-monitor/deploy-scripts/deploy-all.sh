#!/bin/bash
set -uo pipefail; source ~/.service-env 2>/dev/null
echo "═══ Deploy All ═══"; ERRORS=0
for s in deploy-frontend deploy-backend deploy-rpi3; do
    echo "--- $s ---"; ~/deploy/$s.sh || ERRORS=$((ERRORS+1))
done
~/deploy/verify.sh || ERRORS=$((ERRORS+1))
echo ""; [ "$ERRORS" -eq 0 ] && echo "✓ All OK" || echo "✗ $ERRORS errors"
exit "$ERRORS"
