#!/bin/bash
set -euo pipefail

ENVIRONMENT="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "╔══════════════════════════════════════════╗"
echo "║  DOCKFRA APP — Initialization            ║"
echo "╚══════════════════════════════════════════╝"
echo "Environment: $ENVIRONMENT"

# Generate developer SSH keys
bash "$SCRIPT_DIR/generate-developer-keys.sh" "$PROJECT_ROOT"

# Load environment config
if [ "$ENVIRONMENT" = "local" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
        cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Dockfra App — Local Development
ENVIRONMENT=local
COMPOSE_PROJECT_NAME=dockfra-app
APP_NAME=dockfra
APP_VERSION=0.3.0
DEPLOY_MODE=local
DOMAIN=localhost

# SSH Developer
SSH_DEVELOPER_PORT=2200
DEVELOPER_LLM_MODEL=gpt-4o-mini
DEVELOPER_LLM_API_KEY=sk-or-v1-...

# Hosts
FRONTEND_HOST=frontend.localhost
BACKEND_HOST=backend.localhost
MOBILE_HOST=mobile.localhost
DESKTOP_HOST=desktop.localhost

# Services
TRAEFIK_HTTP_PORT=80
TRAEFIK_HTTPS_PORT=443
TRAEFIK_DASHBOARD_PORT=8080
BACKEND_PORT=8081
MOBILE_BACKEND_PORT=8082
DESKTOP_APP_PORT=8083

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=dockfra_app
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379
REDIS_PASSWORD=redis_local

# Git
GIT_REPO_URL=
GIT_BRANCH=main

# SSH Bastions
SSH_FRONTEND_PORT=2222
SSH_BACKEND_PORT=2223
SSH_RPI3_PORT=2224
SSH_DEPLOY_USER=deployer

# RPi3
RPI3_HOST=127.0.0.1
RPI3_USER=pi
RPI3_SSH_PORT=22
RPI3_VNC_PASSWORD=rpi3vnc
VNC_RPI3_PORT=6080

# ACME (Let's Encrypt)
ACME_EMAIL=admin@localhost
ACME_STORAGE=/certs/acme.json

# Health checks
HEALTHCHECK_INTERVAL=30s
HEALTHCHECK_TIMEOUT=10s
HEALTHCHECK_RETRIES=3

# Debug
APP_DEBUG=true
SECRET_KEY=local-dev-secret
EOF
        echo "✅ Created .env.local"
    else
        echo "⚠️  .env.local already exists"
    fi
elif [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "prod" ]; then
    ENVIRONMENT="production"
    if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
        cat > "$PROJECT_ROOT/.env.production" << 'EOF'
# Dockfra App — Production
ENVIRONMENT=production
COMPOSE_PROJECT_NAME=dockfra-app-prod
APP_NAME=dockfra
APP_VERSION=0.3.0
DEPLOY_MODE=production
DOMAIN=yourdomain.com

SSH_DEVELOPER_PORT=2200
DEVELOPER_LLM_API_KEY=${OPENROUTER_API_KEY}

FRONTEND_HOST=frontend.yourdomain.com
BACKEND_HOST=backend.yourdomain.com
MOBILE_HOST=mobile.yourdomain.com
DESKTOP_HOST=desktop.yourdomain.com

BACKEND_PORT=8081
MOBILE_BACKEND_PORT=8082
DESKTOP_APP_PORT=8083

POSTGRES_USER=postgres
POSTGRES_PASSWORD=CHANGE_THIS
POSTGRES_DB=dockfra_app_prod
POSTGRES_PORT=5432

REDIS_PORT=6379
REDIS_PASSWORD=CHANGE_THIS

GIT_REPO_URL=
GIT_BRANCH=main

SSH_FRONTEND_PORT=2222
SSH_BACKEND_PORT=2223
SSH_RPI3_PORT=2224
SSH_DEPLOY_USER=deployer

RPI3_HOST=192.168.1.100
RPI3_USER=pi
RPI3_SSH_PORT=22

ACME_EMAIL=admin@yourdomain.com
ACME_STORAGE=/certs/acme.json

APP_DEBUG=false
SECRET_KEY=CHANGE_THIS
EOF
        echo "✅ Created .env.production"
        echo "⚠️  Please update passwords and domain in .env.production"
    else
        echo "⚠️  .env.production already exists"
    fi
else
    echo "❌ Unknown environment: $ENVIRONMENT"
    echo "   Usage: ./scripts/init.sh [local|production]"
    exit 1
fi

# Create docker network if local
if [ "$ENVIRONMENT" = "local" ]; then
    docker network create dockfra-shared 2>/dev/null || true
    echo "✅ Docker network 'dockfra-shared' created/exists"
fi

# Create shared directories
mkdir -p "$PROJECT_ROOT/shared/tickets"
mkdir -p "$PROJECT_ROOT/shared/logs"
mkdir -p "$PROJECT_ROOT/frontend/public/downloads"

echo ""
echo "✅ App initialization complete!"
echo ""
echo "Next steps:"
if [ "$ENVIRONMENT" = "local" ]; then
    echo "  1. Review .env.local"
    echo "  2. Start app:        docker compose up -d"
    echo "  3. Start management: cd ../management && docker compose up -d"
else
    echo "  1. Edit .env.production with real values"
    echo "  2. Copy management public keys to ssh-developer/keys/authorized_keys"
    echo "  3. Run: docker compose -f docker-compose-production.yml up -d"
fi
echo ""
echo "  SSH Access:"
echo "    Developer: ssh developer@localhost -p 2200"
