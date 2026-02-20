#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
KEYS_DIR="${PROJECT_DIR}/keys"

echo "╔══════════════════════════════════════════╗"
echo "║  DOCKFRA SETUP (LEGACY)                  ║"
echo "╚══════════════════════════════════════════╝"

mkdir -p "$KEYS_DIR"
[ ! -f "${KEYS_DIR}/deployer" ] && {
    ssh-keygen -t ed25519 -f "${KEYS_DIR}/deployer" -N "" -C "dockfra"
    echo "[✓] SSH keys generated"
} || echo "[✓] SSH keys exist"

if [ "${1:-}" = "production" ] || [ "${1:-}" = "prod" ]; then
    cp "${PROJECT_DIR}/.env.production" "${PROJECT_DIR}/.env"
    echo "[✓] Production .env"
else
    [ -f "${PROJECT_DIR}/.env.local" ] && cp "${PROJECT_DIR}/.env.local" "${PROJECT_DIR}/.env"
    echo "[✓] Local .env"
fi

mkdir -p "${PROJECT_DIR}/frontend/public/downloads"

echo ""
echo "  Start:  docker compose build && docker compose up -d"
echo ""
echo "  SSH Access:"
echo "    Manager:   ssh manager@localhost -p 2202"
echo "    Autopilot: ssh autopilot@localhost -p 2203"
echo "    Developer: ssh developer@localhost -p 2200"
echo "    Monitor:   ssh monitor@localhost -p 2201"
