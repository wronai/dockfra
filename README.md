# Dockfra: Generic Docker Infrastructure Manager with AI Agents

**Manage any Docker Compose project** with an interactive web wizard, auto-discovery,
SSH-isolated AI agents, ticket-driven workflows, and autonomous orchestration.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)]()
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)]()

## Key Features

- **Zero-config auto-discovery** — scans for `docker-compose.yml`, parses `${VAR:-default}` env vars (55+ auto-detected)
- **Web setup wizard** — chat-based UI with inline forms, smart suggestions, ⚡ auto-detect, 10 languages
- **SSH role isolation** — 4 agent roles (Developer, Manager, Monitor, Autopilot) in isolated containers
- **LLM integration** — AI error analysis, code review, pair programming, autonomous orchestration via OpenRouter
- **Ticket-driven workflows** — create → assign → implement → review → deploy → close
- **Works with any project** — just point at a directory with `docker-compose.yml`

## 📖 Documentation

| Document | Description |
|---|---|
| **[Getting Started](docs/GETTING-STARTED.md)** | Quickstart for any Docker project |
| **[Architecture](docs/ARCHITECTURE.md)** | System design, modules, data flow (3807 lines, 135 functions, 8 modules) |
| **[Configuration](docs/CONFIGURATION.md)** | `dockfra.yaml`, ENV_SCHEMA, auto-discovery layers |
| **[SSH Roles](docs/SSH-ROLES.md)** | Role separation, commands, isolation |
| **[Wizard API](docs/WIZARD-API.md)** | REST + WebSocket API reference |
| **[Comparisons](comparisons/README.md)** | vs Kamal, Coolify, Portainer, CrewAI, OpenDevin |

## Quick Start

### Any Docker Compose Project

```bash
pip install -e .
cd /path/to/your-project       # must have subdirs with docker-compose.yml
python -m dockfra --root .     # Open http://localhost:5050
```

The wizard auto-discovers stacks, parses env vars, generates a settings UI, and launches everything.

### Full Dockfra Infrastructure

```bash
git clone <repo> dockfra && cd dockfra
make wizard                    # Web wizard at http://localhost:5050
# or manually:
make init && make up           # Generate keys, start all stacks
```

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ LOCAL: Single host ({prefix}-shared network bridge)            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  management/                        app/ (auto-cloned)         │
│  ┌──────────────────────────┐      ┌───────────────────────┐   │
│  │ docker-compose.yml       │      │ docker-compose.yml    │   │
│  │ • ssh-manager   :2202    │      │ • ssh-developer :2200 │   │
│  │ • ssh-autopilot :2203    │◄────►│ • frontend      :80   │   │
│  │ • ssh-monitor   :2201    │shared│ • backend       :8081 │   │
│  │ └─ keys/ (auto-generated)│ net  │ • db, redis, etc      │   │
│  └──────────────────────────┘      └───────────────────────┘   │
│                                                                │
│  dockfra/ (Python package)          shared/                    │
│  ┌──────────────────────────┐      ┌───────────────────────┐   │
│  │ core.py    — foundation  │      │ Dockerfile.ssh-base   │   │
│  │ app.py     — web + API   │      │ ssh-base-init.sh      │   │
│  │ steps.py   — wizard flow │      │ lib/ (llm, tickets)   │   │
│  │ fixes.py   — auto-repair │      └───────────────────────┘   │
│  │ discover.py— role scan   │                                  │
│  │ cli.py     — CLI         │      dockfra.yaml (optional)     │
│  └──────────────────────────┘                                  │
└────────────────────────────────────────────────────────────────┘
```

### Auto-Discovery System

```python
# 1. Stacks: scan ROOT for subdirs with docker-compose.yml
STACKS = {"app": Path, "management": Path, "devices": Path}

# 2. Env vars: parse ${VAR:-default} from all compose files
_COMPOSE_VARS = {"POSTGRES_USER": {"default": "myapp", "stack": "app", "type": "text"}, ...}

# 3. Schema: merge core + discovered + dockfra.yaml overrides
ENV_SCHEMA = _build_env_schema()  # 62 entries (8 core + 54 discovered)

# 4. State mapping: auto-generated from schema
_ENV_TO_STATE = {e["key"]: e["key"].lower() for e in ENV_SCHEMA}
```

### Rebranding

```bash
DOCKFRA_PREFIX=myapp python -m dockfra --root .
# → myapp-shared (network), myapp-ssh-base (image), myapp-traefik (container)
```

## Role Separation

| Capability | Manager | Autopilot | Developer | Monitor |
|---|:---:|:---:|:---:|:---:|
| Create/manage tickets | ✓ | ✓ | — | — |
| SSH to all services | ✓ | ✓ | — | — |
| Configure LLM per role | ✓ | — | — | — |
| Edit code / git push | — | — | ✓ | — |
| AI pair programming | — | — | ✓ | — |
| Deploy to production | — | — | — | ✓ |
| Health monitoring daemon | — | — | — | ✓ |
| Autonomous orchestration | — | ✓ | — | — |

Each role runs in an isolated Docker container with independent LLM config. See [SSH Roles](docs/SSH-ROLES.md).

## Setup Wizard

Chat-based web UI at `http://localhost:5050` with three panels:

| Panel | Features |
|---|---|
| 💬 **Chat** | Step-by-step config, inline forms, AI chat, ⚡ auto-detect, smart chips |
| ⚙️ **Processes** | Container status, stop/restart/port-change actions |
| 📋 **Logs** | Streaming Docker Compose output, error analysis |

### Key wizard capabilities:
- **Auto-discover** stacks and env vars from `docker-compose.yml`
- **Field descriptions** with ℹ️ help buttons, ⚡ auto-detect for git/version
- **Smart suggestions** — git config, SSH keys, ARP devices, free ports, random secrets
- **10 languages** — pl, en, de, fr, es, it, pt, cs, ro, nl
- **Docker error analysis** → interactive fix buttons
- **Git clone integration** — clone app repo on first launch if `GIT_REPO_URL` is set
- **Dashboard** at `/dashboard` — real-time container status + decision log

See [Wizard API](docs/WIZARD-API.md) for REST + WebSocket reference.

## Customization with `dockfra.yaml`

```yaml
# dockfra.yaml — optional project config
lang: pl

env:
  POSTGRES_PASSWORD:
    label: "Database Password"
    group: Database
    type: password
    desc: "PostgreSQL password. Generate random."
  MY_CUSTOM_VAR:
    label: "Custom Setting"
    group: Custom
    default: "value"
```

See [Configuration](docs/CONFIGURATION.md) for full reference.

## Ticket-Driven Workflow

```
Manager creates ticket ──► /shared/tickets/T-0001.json ──► Developer picks up
      │                            ▲                              │
      │ ticket-push T-0001         │ ticket-pull                  │ ticket-done
      ▼                            │                              ▼
  GitHub Issues ◄──────────────────┘                     status=closed
```

## Makefile Reference

```bash
make help                    # Show all targets
```

| Target | Description |
|---|---|
| `make wizard` | Start web wizard at `:5050` |
| `make init` / `make up` / `make down` | Initialize / start / stop stacks |
| `make clone-app` | Clone app repo from `GIT_REPO_URL` |
| `make ssh-developer` | SSH into developer (port 2200) |
| `make ssh-manager` / `ssh-monitor` / `ssh-autopilot` | SSH into other roles |
| `make setup-all` | GitHub keys + LLM + dev tools |
| `make test` | Full test suite (70 tests) |
| `make ps` | Show running containers |

## Project Structure

```
dockfra/
├── dockfra/                    # ══ PYTHON PACKAGE (3807 lines, 135 functions) ══
│   ├── core.py                 # Foundation: config, discovery, Flask, UI helpers (1012 lines)
│   ├── app.py                  # Web server, API routes, SocketIO (652 lines)
│   ├── steps.py                # Wizard step functions (645 lines)
│   ├── fixes.py                # Auto-repair functions (530 lines)
│   ├── discover.py             # SSH role & command discovery (345 lines)
│   ├── cli.py                  # Click CLI (438 lines)
│   ├── llm_client.py           # OpenRouter LLM client (108 lines)
│   ├── templates/              # index.html, dashboard.html
│   └── static/                 # wizard.js, wizard.css
├── shared/                     # ══ SHARED RESOURCES ══
│   ├── Dockerfile.ssh-base     # Universal SSH base image
│   ├── ssh-base-init.sh        # Shared entrypoint init
│   └── lib/                    # llm_client.py, ticket_system.py, logger.py
├── management/                 # ══ MANAGEMENT STACK ══
│   ├── docker-compose.yml      # ssh-manager, ssh-autopilot, ssh-monitor, desktop
│   ├── ssh-manager/            # Tickets, config, planning
│   ├── ssh-autopilot/          # Autonomous LLM orchestration
│   └── ssh-monitor/            # Deploy, health, monitoring
├── app/                        # ══ APP STACK (auto-cloned from GIT_REPO_URL) ══
│   ├── docker-compose.yml      # Your app services + ssh-developer
│   └── ssh-developer/          # AI-powered dev workspace
├── devices/                    # ══ DEVICES STACK (optional) ══
│   └── docker-compose.yml      # ssh-rpi3, vnc-rpi3
├── docs/                       # Detailed documentation
├── comparisons/                # vs Kamal, Coolify, Portainer, CrewAI, OpenDevin
├── tests/                      # 70 tests (60 unit + 10 integration)
├── Makefile                    # Operational targets
├── dockfra.yaml                # Optional project config
└── CHANGELOG.md / TODO.md
```

## Comparisons

See [comparisons/](comparisons/README.md) for detailed analysis:

| vs | Category | Key difference |
|---|---|---|
| [Kamal](comparisons/vs-kamal.md) | Deployment | Dockfra = ongoing manager; Kamal = deploy pipeline |
| [Coolify](comparisons/vs-coolify.md) | Self-hosted PaaS | Dockfra = Docker Compose native; Coolify = Heroku-like |
| [Portainer](comparisons/vs-portainer.md) | Docker GUI | Dockfra = project-specific + AI; Portainer = infra-wide |
| [CrewAI/AutoGen](comparisons/vs-multi-agent-frameworks.md) | Multi-agent AI | Dockfra = real OS containers; CrewAI = Python processes |
| [OpenDevin/Aider](comparisons/vs-ai-dev-agents.md) | AI dev agents | Dockfra = full DevOps lifecycle; OpenDevin = code writing |

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
