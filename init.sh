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

# 1. Initialize app (developer needs keys first)
echo "━━━ Step 1: Initializing app... ━━━"
bash "$SCRIPT_DIR/app/scripts/init.sh" "$ENVIRONMENT"
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
