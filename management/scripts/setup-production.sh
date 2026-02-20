#!/bin/bash

echo "🌍 Setting up PRODUCTION environment..."

PROJECT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

# Create .env.production if not exists
if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
    cat > "$PROJECT_ROOT/.env.production" << 'EOF'
# Dockfra Management — Production
ENVIRONMENT=production
COMPOSE_PROJECT_NAME=dockfra-management-prod

# Networking (remote SSH tunneling)
DEVELOPER_HOST=${DEVELOPER_HOST:-your-app.example.com}
DEVELOPER_PORT=2200
DEVELOPER_SSH_KEY=/root/.ssh/id_ed25519

# SSH ports (exposed to host)
SSH_MANAGER_PORT=2202
SSH_AUTOPILOT_PORT=2203
SSH_MONITOR_PORT=2201

# LLM Configuration
MANAGER_LLM_MODEL=anthropic/claude-sonnet-4
MANAGER_LLM_API_KEY=${OPENROUTER_API_KEY}

AUTOPILOT_LLM_MODEL=anthropic/claude-sonnet-4
AUTOPILOT_LLM_API_KEY=${OPENROUTER_API_KEY}

MONITOR_LLM_MODEL=openai/gpt-4o
MONITOR_LLM_API_KEY=${OPENROUTER_API_KEY}

# Autopilot Settings
AUTOPILOT_INTERVAL=300
AUTOPILOT_MAX_CONCURRENT_TASKS=3

# Logging
LOG_LEVEL=INFO
LOG_DRIVER=json-file

# Backups
BACKUP_ENABLED=true
BACKUP_SCHEDULE=0 2 * * *
BACKUP_RETENTION_DAYS=30

# Health checks
HEALTH_CHECK_INTERVAL=60s
EOF
    echo "✅ Created .env.production"
    echo "⚠️  Please update DEVELOPER_HOST and API keys in .env.production"
else
    echo "⚠️  .env.production already exists"
fi
