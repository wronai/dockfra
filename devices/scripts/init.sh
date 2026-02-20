#!/bin/bash
set -euo pipefail

ENVIRONMENT="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════╗"
echo "║  DOCKFRA DEVICES — Initialization        ║"
echo "╚══════════════════════════════════════════╝"
echo "Environment: $ENVIRONMENT"

# Create .env if not exists
if [ "$ENVIRONMENT" = "local" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
        cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Dockfra Devices — Local
ENVIRONMENT=local
COMPOSE_PROJECT_NAME=dockfra-devices

# RPi3 target device
RPI3_HOST=192.168.1.100
RPI3_USER=pi
RPI3_SSH_PORT=22
RPI3_VNC_PASSWORD=rpi3vnc

# Ports
SSH_RPI3_PORT=2224
VNC_RPI3_PORT=6080

# Display
DISPLAY_WIDTH=1280
DISPLAY_HEIGHT=720

# Deploy
SSH_DEPLOY_USER=deployer
APP_NAME=dockfra
DEPLOY_MODE=local
EOF
        echo "✅ Created .env.local"
        echo "⚠️  Set RPI3_HOST to your RPi3 IP address"
    else
        echo "⚠️  .env.local already exists"
    fi
elif [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "prod" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
        cat > "$PROJECT_ROOT/.env.production" << 'EOF'
# Dockfra Devices — Production
ENVIRONMENT=production
COMPOSE_PROJECT_NAME=dockfra-devices-prod

RPI3_HOST=192.168.1.100
RPI3_USER=pi
RPI3_SSH_PORT=22
RPI3_VNC_PASSWORD=CHANGE_THIS

SSH_RPI3_PORT=2224
VNC_RPI3_PORT=6080

DISPLAY_WIDTH=1280
DISPLAY_HEIGHT=720

SSH_DEPLOY_USER=deployer
APP_NAME=dockfra
DEPLOY_MODE=production
EOF
        echo "✅ Created .env.production"
        echo "⚠️  Set RPI3_HOST and RPI3_VNC_PASSWORD"
    else
        echo "⚠️  .env.production already exists"
    fi
else
    echo "❌ Unknown environment: $ENVIRONMENT"
    echo "   Usage: ./scripts/init.sh [local|production]"
    exit 1
fi

# Create shared network (local only)
if [ "$ENVIRONMENT" = "local" ]; then
    docker network create dockfra-shared 2>/dev/null || true
    echo "✅ Docker network 'dockfra-shared' created/exists"
fi

# Create keys directory placeholder
mkdir -p "$PROJECT_ROOT/keys"
touch "$PROJECT_ROOT/keys/.gitkeep"

echo ""
echo "✅ Devices initialization complete!"
echo ""
echo "Next steps:"
if [ "$ENVIRONMENT" = "local" ]; then
    echo "  1. Edit .env.local — set RPI3_HOST"
    echo "  2. Copy SSH keys:  bash scripts/setup-keys.sh"
    echo "  3. Start:          docker compose up -d"
    echo "  4. Deploy to RPi3: bash scripts/deploy.sh"
else
    echo "  1. Edit .env.production — set RPI3_HOST, RPI3_VNC_PASSWORD"
    echo "  2. docker compose -f docker-compose-production.yml up -d"
fi
