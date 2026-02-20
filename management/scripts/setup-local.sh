#!/bin/bash

echo "🏠 Setting up LOCAL environment..."

PROJECT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

# Create .env.local if not exists
if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
    cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Dockfra Management — Local Development
ENVIRONMENT=local
COMPOSE_PROJECT_NAME=dockfra-management

# Networking (local: shared docker network)
DEVELOPER_HOST=ssh-developer
DEVELOPER_PORT=2222
DEVELOPER_NETWORK=dockfra-shared

# SSH Manager
SSH_MANAGER_PORT=2202
MANAGER_LLM_MODEL=gpt-4o-mini
MANAGER_LLM_API_KEY=sk-or-v1-...

# SSH Autopilot
SSH_AUTOPILOT_PORT=2203
AUTOPILOT_INTERVAL=60
AUTOPILOT_LLM_MODEL=gpt-4o-mini
AUTOPILOT_LLM_API_KEY=sk-or-v1-...

# SSH Monitor
SSH_MONITOR_PORT=2201
MONITOR_LLM_MODEL=gpt-4o-mini
MONITOR_LLM_API_KEY=sk-or-v1-...

# Shared volumes
SHARED_VOLUME=./shared

# Health checks
HEALTH_CHECK_INTERVAL=30s
EOF
    echo "✅ Created .env.local"
else
    echo "⚠️  .env.local already exists"
fi

# Create shared directories
mkdir -p "$PROJECT_ROOT/shared/tickets"
mkdir -p "$PROJECT_ROOT/shared/logs"
mkdir -p "$PROJECT_ROOT/shared/backups"

echo "✅ Local shared directories created"
