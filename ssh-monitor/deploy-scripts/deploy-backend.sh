#!/bin/bash
echo "[deploy:backend] via ssh-backend..."
ssh ssh-backend "
curl -sf http://backend:${BACKEND_PORT:-8081}/health && echo 'backend ✓'
curl -sf http://backend:${BACKEND_PORT:-8081}/db-status && echo 'db ✓'
curl -sf http://mobile-backend:${MOBILE_BACKEND_PORT:-8082}/health && echo 'mobile ✓'
" 2>&1 || echo "⚠ SSH failed"
