#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-local}"

echo "╔══════════════════════════════════════════╗"
echo "║  DOCKFRA MANAGEMENT — Initialization     ║"
echo "╚══════════════════════════════════════════╝"
echo "Environment: $ENVIRONMENT"

# Load environment-specific config
if [ "$ENVIRONMENT" = "local" ]; then
    source "$SCRIPT_DIR/setup-local.sh"
elif [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "prod" ]; then
    ENVIRONMENT="production"
    source "$SCRIPT_DIR/setup-production.sh"
else
    echo "❌ Unknown environment: $ENVIRONMENT"
    echo "   Usage: ./scripts/init.sh [local|production]"
    exit 1
fi

# Generate SSH keys
bash "$SCRIPT_DIR/generate-keys.sh" "$PROJECT_ROOT"

# Create shared network (local only)
if [ "$ENVIRONMENT" = "local" ]; then
    docker network create dockfra-shared 2>/dev/null || true
    echo "✅ Docker network 'dockfra-shared' created/exists"
fi

# Create shared directories
mkdir -p "$PROJECT_ROOT/shared/tickets"
mkdir -p "$PROJECT_ROOT/shared/logs"
mkdir -p "$PROJECT_ROOT/shared/backups"

# Copy public keys to app developer (if on same host)
if [ "$ENVIRONMENT" = "local" ] && [ -d "$PROJECT_ROOT/../app" ]; then
    echo "📋 Syncing SSH keys to developer..."
    bash "$SCRIPT_DIR/sync-keys-to-developer.sh"
fi

echo ""
echo "✅ Management initialization complete!"
echo ""
echo "Next steps:"
if [ "$ENVIRONMENT" = "local" ]; then
    echo "  1. Review .env.local"
    echo "  2. Start app first:  cd ../app && docker compose up -d"
    echo "  3. Start management: docker compose up -d"
else
    echo "  1. Edit .env.production with real API keys and DEVELOPER_HOST"
    echo "  2. Run: docker compose -f docker-compose-production.yml up -d"
fi
