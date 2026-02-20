#!/bin/bash
source ~/.service-env 2>/dev/null; export PYTHONPATH="/shared/lib:$PYTHONPATH"
echo ""; echo "─── HTTP Services ───"
for s in "frontend:80" "backend:${BACKEND_PORT:-8081}" "mobile-backend:${MOBILE_BACKEND_PORT:-8082}" "desktop-app:${DESKTOP_APP_PORT:-8083}"; do
    IFS=':' read -r n p <<< "$s"
    r=$(curl -sf "http://$n:$p/health" 2>/dev/null)
    [ -n "$r" ] && printf "  ✓ %-20s ok\n" "$n" || printf "  ✗ %-20s down\n" "$n"
done
echo ""; echo "─── SSH Channels ───"
for t in "ssh-frontend:${SSH_FRONTEND_PORT:-2222}" "ssh-backend:${SSH_BACKEND_PORT:-2222}" "ssh-rpi3:${SSH_RPI3_PORT:-2222}"; do
    IFS=':' read -r h p <<< "$t"
    timeout 3 bash -c "echo >/dev/tcp/$h/$p" 2>/dev/null && printf "  ✓ %-20s up\n" "$h" || printf "  ✗ %-20s down\n" "$h"
done
echo ""; echo "─── Git ───"
[ -d /repo/.git ] && (cd /repo && echo "  HEAD: $(git rev-parse --short HEAD 2>/dev/null)  Last deployed: $(cat ~/.last-deployed-commit 2>/dev/null | head -c 8)")
echo ""
