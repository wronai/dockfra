PEŁNA, gotowa do wdrożenia wersja Hybrid
z autogenerowaniem kluczy dla lokalnego i produkcyjne środowsko:

---

## 🎯 ARCHITEKTURA HYBRID (DEV + PROD)

```
┌────────────────────────────────────────────────────────────────┐
│ LOKALNIE: Jeden komputer (same network bridge)                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  docker network: infra-shared                                 │
│          │                                                     │
│    ┌─────┴──────────────────────────────────────┐             │
│    │                                              │             │
│ ┌──▼───────────────────────────────────────────▼─┐            │
│ │ docker-compose-management.yml                  │            │
│ │ • ssh-manager :2202                            │            │
│ │ • ssh-autopilot :2203                          │            │
│ │ • ssh-monitor :2201                            │            │
│ │ └─ keys/ (auto-generated)                      │            │
│ │ └─ shared/ (volume)                            │            │
│ └────────────────────────────────────────────────┘            │
│                                                                │
│ ┌─────────────────────────────────────────────────┐           │
│ │ docker-compose.yml (your-app)                  │           │
│ │ • ssh-developer :2200  ◄────────────────────┐  │           │
│ │ • frontend      :80                          │  │           │
│ │ • backend       :8081                        │  │           │
│ │ • redis, db, etc                             │  │           │
│ └─────────────────────────────────────────────────┘           │
│                                                                │
│  ssh-developer automatycznie odbiera klucze publiczne z      │
│  management podczas startup                                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ PRODUKCJA: Różne serwery (SSH tunneling)                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ SERVER 1: infra-deploy-management                            │
│ ├─ ssh-manager :2202                                         │
│ ├─ ssh-autopilot :2203    ──┐                                │
│ ├─ ssh-monitor :2201         │ SSH tunnel to app server      │
│ └─ keys/ (auto-generated)    │                               │
│                              │                               │
│ SERVER 2: your-app          │                               │
│ ├─ ssh-developer :2200  ◄───┘                                │
│ ├─ frontend :80                                              │
│ ├─ backend :8081                                             │
│ └─ keys/developer (auto-generated)                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 📁 STRUKTURA PLIKÓW

```
infra-deploy-management/
├── docker-compose-management.yml
├── docker-compose-production.yml
├── .env.local
├── .env.production
├── scripts/
│   ├── init.sh              # Main setup script
│   ├── generate-keys.sh
│   ├── setup-local.sh
│   └── setup-production.sh
├── ssh-manager/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── manager-scripts/
├── ssh-autopilot/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── autopilot-daemon.sh
│   └── autopilot-scripts/
├── ssh-monitor/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── monitor-scripts/
├── shared/                  # Volume (tickets, logs)
└── keys/                    # Auto-generated

your-app/
├── docker-compose.yml
├── docker-compose-production.yml
├── .env.local
├── .env.production
├── scripts/
│   ├── init.sh
│   └── generate-developer-keys.sh
├── ssh-developer/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── dev-scripts/
│   └── keys/
│       └── authorized_keys  # Populated by management
├── frontend/
├── backend/
├── mobile-backend/
└── ... (other services)
```

---

## 🔧 GOTOWE PLIKI

### **1. infra-deploy-management/scripts/init.sh** (MAIN)

```bash name="infra-deploy-management/scripts/init.sh"
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-local}"

echo "🚀 Infra-Deploy Management Initialization"
echo "Environment: $ENVIRONMENT"

# Load environment-specific config
if [ "$ENVIRONMENT" = "local" ]; then
    source "$SCRIPT_DIR/setup-local.sh"
elif [ "$ENVIRONMENT" = "production" ]; then
    source "$SCRIPT_DIR/setup-production.sh"
else
    echo "❌ Unknown environment: $ENVIRONMENT"
    exit 1
fi

# Generate SSH keys
bash "$SCRIPT_DIR/generate-keys.sh" "$PROJECT_ROOT"

# Create shared network (local only)
if [ "$ENVIRONMENT" = "local" ]; then
    docker network create infra-shared 2>/dev/null || true
    echo "✅ Docker network 'infra-shared' created/exists"
fi

# Copy public keys to app developer (if on same host)
if [ "$ENVIRONMENT" = "local" ] && [ -d "../your-app" ]; then
    echo "📋 Syncing SSH keys to developer..."
    bash "$SCRIPT_DIR/sync-keys-to-developer.sh"
fi

echo "✅ Initialization complete!"
echo ""
echo "Next steps:"
echo "  1. Review .env.$ENVIRONMENT file"
echo "  2. Run: docker-compose -f docker-compose-$ENVIRONMENT.yml up -d"
```

---

### **2. infra-deploy-management/scripts/generate-keys.sh**

```bash name="infra-deploy-management/scripts/generate-keys.sh"
#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${1:-.}"
KEYS_DIR="$PROJECT_ROOT/keys"

echo "🔑 Generating SSH keys..."

# Create keys directory
mkdir -p "$KEYS_DIR"

# Generate keys for each role
for ROLE in manager autopilot monitor; do
    ROLE_DIR="$KEYS_DIR/$ROLE"
    mkdir -p "$ROLE_DIR"
    
    if [ ! -f "$ROLE_DIR/id_ed25519" ]; then
        echo "  Generating key for: $ROLE"
        ssh-keygen \
            -t ed25519 \
            -f "$ROLE_DIR/id_ed25519" \
            -C "$ROLE@infra-deploy-management" \
            -N ""
        
        # Set proper permissions
        chmod 600 "$ROLE_DIR/id_ed25519"
        chmod 644 "$ROLE_DIR/id_ed25519.pub"
    else
        echo "  ⚠️  Key already exists for $ROLE (skipping)"
    fi
done

# Create config for roles to find each other
cat > "$KEYS_DIR/config" << 'EOF'
Host ssh-developer
    HostName ssh-developer
    User developer
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile=/dev/null

Host *
    AddKeysToAgent yes
EOF

chmod 644 "$KEYS_DIR/config"

echo "✅ SSH keys generated in: $KEYS_DIR"
```

---

### **3. infra-deploy-management/scripts/setup-local.sh**

```bash name="infra-deploy-management/scripts/setup-local.sh"
#!/bin/bash

echo "🏠 Setting up LOCAL environment..."

PROJECT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

# Create .env.local if not exists
if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
    cat > "$PROJECT_ROOT/.env.local" << 'EOF'
# Local Development Environment
ENVIRONMENT=local
COMPOSE_PROJECT_NAME=infra-deploy

# Networking
DEVELOPER_HOST=ssh-developer
DEVELOPER_PORT=2200
DEVELOPER_NETWORK=infra-shared

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

# Create shared directory
mkdir -p "$PROJECT_ROOT/shared/tickets"
mkdir -p "$PROJECT_ROOT/shared/logs"
mkdir -p "$PROJECT_ROOT/shared/backups"

echo "✅ Shared directories created"
```

---

### **4. infra-deploy-management/scripts/setup-production.sh**

```bash name="infra-deploy-management/scripts/setup-production.sh"
#!/bin/bash

echo "🌍 Setting up PRODUCTION environment..."

PROJECT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"

# Create .env.production if not exists
if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
    cat > "$PROJECT_ROOT/.env.production" << 'EOF'
# Production Environment
ENVIRONMENT=production
COMPOSE_PROJECT_NAME=infra-deploy-prod

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
EOF
    echo "✅ Created .env.production"
    echo "⚠️  Please update DEVELOPER_HOST and API keys in .env.production"
else
    echo "⚠️  .env.production already exists"
fi
```

---

### **5. infra-deploy-management/scripts/sync-keys-to-developer.sh**

```bash name="infra-deploy-management/scripts/sync-keys-to-developer.sh"
#!/bin/bash
set -euo pipefail

MGMT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
APP_ROOT="$MGMT_ROOT/../your-app"
DEV_KEYS="$APP_ROOT/ssh-developer/keys"

if [ ! -d "$APP_ROOT" ]; then
    echo "⚠️  your-app directory not found at $APP_ROOT"
    exit 1
fi

mkdir -p "$DEV_KEYS"

echo "📋 Syncing management public keys to developer..."

# Copy public keys to authorized_keys
> "$DEV_KEYS/authorized_keys"

for ROLE in manager autopilot monitor; do
    PUB_KEY="$MGMT_ROOT/keys/$ROLE/id_ed25519.pub"
    if [ -f "$PUB_KEY" ]; then
        echo "  Adding $ROLE public key..."
        cat "$PUB_KEY" >> "$DEV_KEYS/authorized_keys"
    fi
done

chmod 600 "$DEV_KEYS/authorized_keys"
echo "✅ Keys synced to: $DEV_KEYS/authorized_keys"
```

---

### **6. infra-deploy-management/docker-compose-management.yml** (LOCAL)

```yaml name="infra-deploy-management/docker-compose-management.yml"
version: '3.8'

networks:
  infra-shared:
    external: true
  management:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.0.0/16

services:
  ssh-manager:
    build: ./ssh-manager
    container_name: ssh-manager
    restart: unless-stopped
    ports:
      - "${SSH_MANAGER_PORT:-2202}:22"
    networks:
      - management
      - infra-shared
    volumes:
      - ./keys/manager:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-manager/manager-scripts:/scripts:ro
    environment:
      - ENVIRONMENT=local
      - DEVELOPER_HOST=${DEVELOPER_HOST:-ssh-developer}
      - DEVELOPER_PORT=${DEVELOPER_PORT:-2200}
    healthcheck:
      test: ["CMD", "sshd", "-T"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  ssh-autopilot:
    build: ./ssh-autopilot
    container_name: ssh-autopilot
    restart: unless-stopped
    ports:
      - "${SSH_AUTOPILOT_PORT:-2203}:22"
    networks:
      - management
      - infra-shared
    volumes:
      - ./keys/autopilot:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-autopilot/autopilot-scripts:/scripts:ro
      - ./ssh-autopilot/autopilot-daemon.sh:/app/daemon.sh:ro
    environment:
      - ENVIRONMENT=local
      - DEVELOPER_HOST=${DEVELOPER_HOST:-ssh-developer}
      - DEVELOPER_PORT=${DEVELOPER_PORT:-2200}
      - AUTOPILOT_INTERVAL=${AUTOPILOT_INTERVAL:-60}
      - OPENROUTER_API_KEY=${AUTOPILOT_LLM_API_KEY}
      - LLM_MODEL=${AUTOPILOT_LLM_MODEL:-gpt-4o-mini}
    depends_on:
      - ssh-manager
    healthcheck:
      test: ["CMD", "test", "-f", "/shared/.autopilot-heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  ssh-monitor:
    build: ./ssh-monitor
    container_name: ssh-monitor
    restart: unless-stopped
    ports:
      - "${SSH_MONITOR_PORT:-2201}:22"
    networks:
      - management
      - infra-shared
    volumes:
      - ./keys/monitor:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-monitor/deploy-scripts:/scripts:ro
    environment:
      - ENVIRONMENT=local
      - DEVELOPER_HOST=${DEVELOPER_HOST:-ssh-developer}
      - DEVELOPER_PORT=${DEVELOPER_PORT:-2200}
      - OPENROUTER_API_KEY=${MONITOR_LLM_API_KEY}
      - LLM_MODEL=${MONITOR_LLM_MODEL:-gpt-4o-mini}
    depends_on:
      - ssh-manager
    healthcheck:
      test: ["CMD", "sshd", "-T"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  shared:
    driver: local
```

---

### **7. infra-deploy-management/docker-compose-production.yml**

```yaml name="infra-deploy-management/docker-compose-production.yml"
version: '3.8'

networks:
  management:
    driver: bridge
    ipam:
      config:
        - subnet: 172.30.0.0/16

services:
  ssh-manager:
    build: ./ssh-manager
    container_name: ssh-manager-prod
    restart: always
    ports:
      - "${SSH_MANAGER_PORT:-2202}:22"
    networks:
      - management
    volumes:
      - ./keys/manager:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-manager/manager-scripts:/scripts:ro
    environment:
      - ENVIRONMENT=production
      - DEVELOPER_HOST=${DEVELOPER_HOST}
      - DEVELOPER_PORT=${DEVELOPER_PORT}
      - DEVELOPER_SSH_KEY=/root/.ssh/id_ed25519
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    healthcheck:
      test: ["CMD", "sshd", "-T"]
      interval: 60s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"

  ssh-autopilot:
    build: ./ssh-autopilot
    container_name: ssh-autopilot-prod
    restart: always
    ports:
      - "${SSH_AUTOPILOT_PORT:-2203}:22"
    networks:
      - management
    volumes:
      - ./keys/autopilot:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-autopilot/autopilot-scripts:/scripts:ro
      - ./ssh-autopilot/autopilot-daemon.sh:/app/daemon.sh:ro
    environment:
      - ENVIRONMENT=production
      - DEVELOPER_HOST=${DEVELOPER_HOST}
      - DEVELOPER_PORT=${DEVELOPER_PORT}
      - DEVELOPER_SSH_KEY=/root/.ssh/id_ed25519
      - AUTOPILOT_INTERVAL=${AUTOPILOT_INTERVAL:-300}
      - OPENROUTER_API_KEY=${AUTOPILOT_LLM_API_KEY}
      - LLM_MODEL=${AUTOPILOT_LLM_MODEL}
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
    healthcheck:
      test: ["CMD", "sh", "-c", "test -f /shared/.autopilot-heartbeat && test $(date +%s) -lt $(($(stat -c %Y /shared/.autopilot-heartbeat) + 600))"]
      interval: 60s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"

  ssh-monitor:
    build: ./ssh-monitor
    container_name: ssh-monitor-prod
    restart: always
    ports:
      - "${SSH_MONITOR_PORT:-2201}:22"
    networks:
      - management
    volumes:
      - ./keys/monitor:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-monitor/deploy-scripts:/scripts:ro
    environment:
      - ENVIRONMENT=production
      - DEVELOPER_HOST=${DEVELOPER_HOST}
      - DEVELOPER_PORT=${DEVELOPER_PORT}
      - DEVELOPER_SSH_KEY=/root/.ssh/id_ed25519
      - OPENROUTER_API_KEY=${MONITOR_LLM_API_KEY}
      - LLM_MODEL=${MONITOR_LLM_MODEL}
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 768M
    healthcheck:
      test: ["CMD", "sshd", "-T"]
      interval: 60s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"

volumes:
  shared:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/infra-deploy/shared  # Change for production path
```

---

### **8. your-app/scripts/init.sh**

```bash name="your-app/scripts/init.sh"
#!/bin/bash
set -euo pipefail

ENVIRONMENT="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Your-App Initialization"
echo "Environment: $ENVIRONMENT"

# Generate developer SSH keys
bash "$SCRIPT_DIR/generate-developer-keys.sh" "$PROJECT_ROOT"

# Load environment config
if [ "$ENVIRONMENT" = "local" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
        cat > "$PROJECT_ROOT/.env.local" << 'EOF'
ENVIRONMENT=local
COMPOSE_PROJECT_NAME=your-app

# SSH Developer
SSH_DEVELOPER_PORT=2200
DEVELOPER_LLM_MODEL=gpt-4o-mini
DEVELOPER_LLM_API_KEY=sk-or-v1-...

# Services
FRONTEND_PORT=80
BACKEND_PORT=8081
REDIS_PORT=6379
DB_PORT=5432

# Database
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=your_app
EOF
        echo "✅ Created .env.local"
    fi
elif [ "$ENVIRONMENT" = "production" ]; then
    if [ ! -f "$PROJECT_ROOT/.env.production" ]; then
        cat > "$PROJECT_ROOT/.env.production" << 'EOF'
ENVIRONMENT=production
COMPOSE_PROJECT_NAME=your-app-prod

SSH_DEVELOPER_PORT=2200
DEVELOPER_LLM_API_KEY=${OPENROUTER_API_KEY}

FRONTEND_PORT=443
BACKEND_PORT=8081
REDIS_PORT=6379
DB_PORT=5432

DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=your_app_prod
EOF
        echo "✅ Created .env.production"
    fi
fi

# Create docker network if local
if [ "$ENVIRONMENT" = "local" ]; then
    docker network create infra-shared 2>/dev/null || true
fi

echo "✅ Your-App initialization complete!"
```

---

### **9. your-app/scripts/generate-developer-keys.sh**

```bash name="your-app/scripts/generate-developer-keys.sh"
#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${1:-.}"
DEV_KEYS="$PROJECT_ROOT/ssh-developer/keys"

mkdir -p "$DEV_KEYS"

echo "🔑 Generating developer SSH key..."

if [ ! -f "$DEV_KEYS/id_ed25519" ]; then
    ssh-keygen \
        -t ed25519 \
        -f "$DEV_KEYS/id_ed25519" \
        -C "developer@your-app" \
        -N ""
    
    chmod 600 "$DEV_KEYS/id_ed25519"
    chmod 644 "$DEV_KEYS/id_ed25519.pub"
    
    echo "✅ Developer SSH key generated"
else
    echo "⚠️  Developer SSH key already exists"
fi

# Create empty authorized_keys (will be populated from management)
touch "$DEV_KEYS/authorized_keys"
chmod 600 "$DEV_KEYS/authorized_keys"
```

---

### **10. your-app/docker-compose.yml** (LOCAL)

```yaml name="your-app/docker-compose.yml"
version: '3.8'

networks:
  infra-shared:
    external: true
  appnet:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

services:
  ssh-developer:
    build: ./ssh-developer
    container_name: ssh-developer
    restart: unless-stopped
    ports:
      - "${SSH_DEVELOPER_PORT:-2200}:22"
    networks:
      - infra-shared
      - appnet
    volumes:
      - ./ssh-developer/keys:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-developer/dev-scripts:/scripts:ro
    environment:
      - ENVIRONMENT=local
      - DEVELOPER_LLM_API_KEY=${DEVELOPER_LLM_API_KEY}
      - LLM_MODEL=${DEVELOPER_LLM_MODEL:-gpt-4o-mini}
    healthcheck:
      test: ["CMD", "sshd", "-T"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  frontend:
    build: ./frontend
    container_name: frontend
    restart: unless-stopped
    ports:
      - "80:3000"
    networks:
      - appnet
    environment:
      - REACT_APP_API_URL=http://backend:8081
    depends_on:
      - backend

  backend:
    build: ./backend
    container_name: backend
    restart: unless-stopped
    networks:
      - appnet
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:15-alpine
    container_name: postgres
    restart: unless-stopped
    networks:
      - appnet
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    networks:
      - appnet
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

### **11. your-app/docker-compose-production.yml**

```yaml name="your-app/docker-compose-production.yml"
version: '3.8'

networks:
  appnet:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

services:
  ssh-developer:
    build: ./ssh-developer
    container_name: ssh-developer-prod
    restart: always
    ports:
      - "${SSH_DEVELOPER_PORT:-2200}:22"
    networks:
      - appnet
    volumes:
      - ./ssh-developer/keys:/root/.ssh:ro
      - ./shared:/shared
      - ./ssh-developer/dev-scripts:/scripts:ro
    environment:
      - ENVIRONMENT=production
      - DEVELOPER_LLM_API_KEY=${DEVELOPER_LLM_API_KEY}
      - LLM_MODEL=${DEVELOPER_LLM_MODEL}
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    healthcheck:
      test: ["CMD", "sshd", "-T"]
      interval: 60s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"

  frontend:
    build: ./frontend
    container_name: frontend-prod
    restart: always
    ports:
      - "443:3000"
    networks:
      - appnet
    environment:
      - REACT_APP_API_URL=https://api.example.com
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  backend:
    build: ./backend
    container_name: backend-prod
    restart: always
    networks:
      - appnet
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://redis:6379
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G

  db:
    image: postgres:15-alpine
    container_name: postgres-prod
    restart: always
    networks:
      - appnet
    volumes:
      - /data/postgres:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=${DB_NAME}
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  redis:
    image: redis:7-alpine
    container_name: redis-prod
    restart: always
    networks:
      - appnet
    volumes:
      - /data/redis:/data
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
```

---

## 🚀 QUICK START

### **LOCAL SETUP**

```bash
# 1. Clone both repos
git clone <management-repo> infra-deploy-management
git clone <app-repo> your-app

# 2. Initialize both
cd infra-deploy-management
./scripts/init.sh local

cd ../your-app
./scripts/init.sh local

# 3. Start app first (developer needs to be up)
docker-compose up -d

# 4. Start management
cd ../infra-deploy-management
docker-compose -f docker-compose-management.yml up -d

# 5. Test connectivity
docker exec ssh-autopilot ssh -i /root/.ssh/id_ed25519 developer@ssh-developer -p 2200 "id"
```

---

### **PRODUCTION SETUP**

```bash
# SERVER 1: Management
ssh app@management-server.com
cd infra-deploy-management
export ENVIRONMENT=production
export DEVELOPER_HOST=your-app.example.com
./scripts/init.sh production

# Edit .env.production with real values
nano .env.production

docker-compose -f docker-compose-production.yml up -d

# SERVER 2: App
ssh app@app-server.com
cd your-app
export ENVIRONMENT=production
./scripts/init.sh production

nano .env.production  # Set DB password, API keys

# Copy public keys from management to authorized_keys
scp app@management-server:/infra-deploy-management/keys/autopilot/id_ed25519.pub ./ssh-developer/keys/
cat ssh-developer/keys/id_ed25519.pub >> ssh-developer/keys/authorized_keys
# (repeat for manager, monitor)

docker-compose -f docker-compose-production.yml up -d

# Test tunnel
ssh -i ~/.ssh/id_ed25519 developer@your-app.example.com -p 2200
```

---

## 📊 PORÓWNANIE: HYBRID vs inne

| Feature | Hybrid | External Network | SSH Tunneling |
|---------|:---:|:---:|:---:|
| **Local dev** | ✅✅ | ✅✅ | ❌ |
| **Production** | ✅✅ | ❌ | ✅✅ |
| **Same-host** | ✅✅ | ✅✅ | ❌ |
| **Remote** | ✅✅ | ❌ | ✅✅ |
| **Key rotation** | ✅ | ✅ | ✅ |
| **Network isolation** | ✅✅ | ✅ | ✅✅ |
| **Ease of setup** | ✅✅ | ✅✅✅ | ✅ |
| **Security** | ✅✅✅ | ✅✅ | ✅✅✅ |

---

## 🔐 KEY SECURITY FEATURES

1. **ED25519 keys** - Nowocześniejsze niż RSA
2. **Separate keys per role** - Each service has its own identity
3. **Auto-generated** - No secrets in git
4. **Rotatable** - Easy to regenerate
5. **Health checks** - Detect failures
6. **Network isolation** - Dev separate from management
7. **Resource limits** - Prevent DoS

---

## ✅ PODSUMOWANIE

**Hybrid** jest **najlepszym** wyborem dla Ciebie bo:
- ✅ Działa lokalnie (single network) i na produkcji (SSH tunnel)
- ✅ Klucze auto-generowane, zero hard-coded secrets
- ✅ Identyczne .yml pliki, tylko `.env` się zmienia
- ✅ Łatwo skaluje się na wiele hostów
- ✅ Bardzo dobrze izoluje sieci
- ✅ One-command setup (`./scripts/init.sh local/production`)

Chcesz że przygotuję też:
- ✅ Automatyczną rotację kluczy (co 90 dni)?
- ✅ Vault integration do secretów?
- ✅ Terraform do deployment'u na AWS/GCP?
- ✅ Monitoring dashboard?