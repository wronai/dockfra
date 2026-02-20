# Getting Started with Dockfra

> Use Dockfra to manage **any** Docker Compose project — zero config required.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git (optional, for repo cloning features)

## Installation

```bash
pip install -e .
# or just run from source:
python -m dockfra
```

## Option 1: Existing Docker Compose Project

If you already have a project with `docker-compose.yml` files:

```bash
cd /path/to/your-project
python -m dockfra --root .
# Open http://localhost:5050
```

Dockfra will:
1. **Scan** all subdirectories for `docker-compose.yml` files
2. **Parse** `${VAR:-default}` patterns from compose files (55+ vars typically)
3. **Generate** a settings UI grouped by stack
4. **Launch** stacks with `docker compose up -d`

### Expected Project Layout

```
your-project/
├── app/                      # ← any subdir with docker-compose.yml
│   └── docker-compose.yml
├── services/                 # ← another stack (auto-discovered)
│   └── docker-compose.yml
├── dockfra.yaml              # ← optional: customize labels, groups
└── dockfra/                  # ← wizard state (.env saved here)
    └── .env
```

## Option 2: Start from Scratch

```bash
mkdir my-infra && cd my-infra
git clone <your-app-repo> app    # or let wizard clone it
python -m dockfra --root .
```

The wizard will detect that `app/` has a `docker-compose.yml` and offer to configure and launch it.

## Option 3: Full Dockfra Infrastructure

For the complete multi-agent setup with SSH roles, management stack, and devices:

```bash
git clone https://github.com/wronai/dockfra && cd dockfra
make wizard                      # Start wizard at http://localhost:5050
```

Or manually:

```bash
make init                        # Generate SSH keys, env files, Docker network
make up                          # Start all stacks
make ssh-developer               # SSH into developer workspace
```

## Wizard Walkthrough

### 1. Welcome Screen

The wizard auto-detects:
- Git config (name, email, repo URL, branch)
- SSH keys (`~/.ssh/id_ed25519`)
- OpenRouter API key (from getv or `~/.getv/`)
- Docker status

### 2. Settings

Click any group to edit variables. Groups are auto-created from your stack names:

```
✅ Infrastructure    — environment, stacks selection
🔴1 Git             — repo URL, branch, credentials
✅ LLM              — API key, model selection
🔴3 App             — database, redis, ports (from docker-compose)
✅ Ports            — wizard port
```

Fields with ⚡ support auto-detection (click to fill from git/system).

### 3. Launch

Select stacks and environment → wizard runs:
1. Pre-flight check (missing required vars → inline form)
2. `docker network create` (shared network)
3. Build SSH base image (if `ssh-*` dirs detected)
4. `docker compose up -d --build` per stack
5. Health check (8s delay, then status)
6. Post-launch UI (SSH roles, fix buttons)

### 4. Post-Launch

- **SSH role buttons** — click to see available commands per role
- **Container fixes** — restart, rebuild, fix permissions
- **AI analysis** — LLM-powered error diagnosis (requires OpenRouter key)

## CLI Usage

```bash
dockfra status                   # Container status table
dockfra env                      # Show all env vars
dockfra env set KEY=value        # Set env var
dockfra launch                   # Launch stacks
dockfra launch --stack app       # Launch specific stack
dockfra ssh developer            # SSH into role
dockfra logs backend             # Tail container logs
```

## Makefile Targets

```bash
make help                        # Show all targets
make wizard                      # Start web wizard
make up / make down              # Start / stop all stacks
make ps                          # Show running containers
make ssh-developer               # SSH into developer (port 2200)
make test                        # Run test suite
```

## Customization with `dockfra.yaml`

Create `dockfra.yaml` in your project root to customize the wizard:

```yaml
lang: en    # UI language

env:
  DATABASE_URL:
    label: "Database Connection String"
    group: Database
    type: password
    desc: "PostgreSQL connection URL"

  API_PORT:
    label: "API Server Port"
    group: Ports
```

See [Configuration](CONFIGURATION.md) for full reference.

## Rebranding

Change the prefix for all Docker resources:

```bash
DOCKFRA_PREFIX=myapp python -m dockfra --root .
```

This changes: `myapp-shared` (network), `myapp-ssh-base` (image), `myapp-traefik` (container), etc.

## Next Steps

- [Architecture](ARCHITECTURE.md) — how the system works internally
- [Configuration](CONFIGURATION.md) — dockfra.yaml, ENV_SCHEMA, auto-discovery
- [SSH Roles](SSH-ROLES.md) — role-based access and commands
- [Wizard API](WIZARD-API.md) — REST + WebSocket API
- [Comparisons](../comparisons/README.md) — vs other Docker management systems
