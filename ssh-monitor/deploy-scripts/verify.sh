#!/bin/bash
P=0; F=0
ck() { local n=$1; shift; if "$@" >/dev/null 2>&1; then printf "  ✓ %-25s\n" "$n"; P=$((P+1)); else printf "  ✗ %-25s\n" "$n"; F=$((F+1)); fi; }
echo "─── Verify ───"
ck "Frontend" curl -sf http://frontend:80/health
ck "Backend" curl -sf "http://backend:${BACKEND_PORT:-8081}/health"
ck "Mobile" curl -sf "http://mobile-backend:${MOBILE_BACKEND_PORT:-8082}/health"
ck "Desktop" curl -sf "http://desktop-app:${DESKTOP_APP_PORT:-8083}/health"
ck "ssh-frontend" timeout 3 bash -c "echo >/dev/tcp/${SSH_FRONTEND_HOST:-ssh-frontend}/${SSH_FRONTEND_PORT:-2222}"
ck "ssh-backend" timeout 3 bash -c "echo >/dev/tcp/${SSH_BACKEND_HOST:-ssh-backend}/${SSH_BACKEND_PORT:-2222}"
ck "ssh-rpi3" timeout 3 bash -c "echo >/dev/tcp/${SSH_RPI3_HOST:-ssh-rpi3}/${SSH_RPI3_PORT:-2222}"
echo "  $P passed, $F failed"; exit "$F"
