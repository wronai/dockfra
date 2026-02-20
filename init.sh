#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVIRONMENT="${1:-local}"

echo "╔══════════════════════════════════════════╗"
echo "║  DOCKFRA — Hybrid Environment Setup      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Environment: $ENVIRONMENT"
echo ""

# 1. Initialize app — app/ is a separate repo (git@github.com:wronai/dockfra-app.git)
#    The wizard clones it automatically on first launch via GIT_REPO_URL.
#    If app/ already exists locally, run its init script.
echo "━━━ Step 1: App stack... ━━━"
if [ -f "$SCRIPT_DIR/app/scripts/init.sh" ]; then
    bash "$SCRIPT_DIR/app/scripts/init.sh" "$ENVIRONMENT"
else
    echo "  ℹ️  app/ not present — will be cloned from GIT_REPO_URL when wizard launches the stack."
    echo "  Run: make wizard   (or open http://localhost:5050)"
fi
echo ""

# 2. Initialize management (generates keys + syncs to developer)
echo "━━━ Step 2: Initializing management... ━━━"
bash "$SCRIPT_DIR/management/scripts/init.sh" "$ENVIRONMENT"
echo ""

echo "╔══════════════════════════════════════════╗"
echo "║  DOCKFRA — Setup Complete!               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Quick Start (local):"
echo "    1. cd app && docker compose up -d"
echo "    2. cd ../management && docker compose up -d"
echo ""
echo "  Quick Start (production):"
echo "    1. cd app && docker compose -f docker-compose-production.yml up -d"
echo "    2. cd ../management && docker compose -f docker-compose-production.yml up -d"
echo ""
echo "  SSH Access:"
echo "    Manager:   ssh manager@localhost -p 2202"
echo "    Autopilot: ssh autopilot@localhost -p 2203"
echo "    Developer: ssh developer@localhost -p 2200"
echo "    Monitor:   ssh monitor@localhost -p 2201"
