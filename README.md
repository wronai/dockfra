# Dockfra: LLM-Powered Role-Based Infrastructure

Multi-service Docker infrastructure with **hybrid architecture** (local + production),
strict role separation, LLM integration via OpenRouter, ticket-driven workflows,
autonomous orchestration, and an **interactive web setup wizard**.

## Hybrid Architecture

The project is split into two independent stacks that communicate via a shared Docker
network (local) or SSH tunneling (production):

```
┌────────────────────────────────────────────────────────────────┐
│ LOCAL: Single host (dockfra-shared network bridge)             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  management/                        app/                       │
│  ┌──────────────────────────┐      ┌───────────────────────┐  │
│  │ docker-compose.yml       │      │ docker-compose.yml    │  │
│  │ • ssh-manager   :2202    │      │ • ssh-developer :2200 │  │
│  │ • ssh-autopilot :2203    │◄────►│ • frontend      :80   │  │
│  │ • ssh-monitor   :2201    │shared│ • backend       :8081 │  │
│  │ └─ keys/ (auto-generated)│ net  │ • db, redis, etc      │  │
│  │ └─ shared/ (tickets,logs)│      │ • ssh-rpi3, vnc-rpi3  │  │
│  └──────────────────────────┘      └───────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ PRODUCTION: Separate servers (SSH tunneling)                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ SERVER 1: dockfra-management       SERVER 2: your-app          │
│ ├─ ssh-manager   :2202             ├─ ssh-developer :2200 ◄─┐ │
│ ├─ ssh-autopilot :2203 ────────────┤ ├─ frontend    :443    │ │
│ ├─ ssh-monitor   :2201    SSH      │ ├─ backend     :8081   │ │
│ └─ keys/ (auto-generated) tunnel   │ └─ db, redis, rpi3    │ │
│                                     └───────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## Role Separation

| Capability | Manager | Autopilot | Developer | Monitor |
|---|:---:|:---:|:---:|:---:|
| Create/manage tickets | ✓ | ✓ | — | — |
| Push tickets to GitHub | ✓ | — | — | — |
| Pull tickets from GitHub | ✓ | — | — | — |
| Configure LLM on services | ✓ | — | — | — |
| Update .env via SSH | ✓ | — | — | — |
| SSH to all role services | ✓ | ✓ | — | — |
| Work on assigned tickets | — | — | ✓ | — |
| Edit code / git push | — | — | ✓ | — |
| Run local tests | — | — | ✓ | — |
| LLM code assistance | — | — | ✓ | — |
| Deploy to production | — | — | **✗** | ✓ |
| SSH to infrastructure bastions | — | — | **✗** | ✓ |
| Health monitoring daemon | — | — | — | ✓ |
| LLM log analysis | — | — | — | ✓ |
| Autonomous LLM orchestration | — | ✓ | — | — |
| Docker socket access | — | — | **✗** | ✓ |

## LLM Integration

Each role service has its own `.env` with independent LLM configuration via **OpenRouter**:

```
app/ssh-developer/.env            → LLM for code reviews, implementation, debugging
management/ssh-monitor/.env       → LLM for log analysis, deployment decisions
management/ssh-manager/.env       → LLM for ticket planning, project management
management/ssh-autopilot/.env     → LLM for autonomous orchestration decisions
```

Configure API key and model per service:
```bash
# From ssh-manager:
config-developer               # View/update developer LLM config
config-monitor                  # View/update monitor LLM config
config-show all                 # View all service configs
```

Supported models (via OpenRouter):
- `anthropic/claude-sonnet-4`
- `openai/gpt-4o` / `openai/gpt-4o-mini`
- `google/gemini-2.0-flash-001`
- `meta-llama/llama-3.1-70b-instruct`
- `deepseek/deepseek-chat-v3-0324`

## Setup Wizard

The fastest way to configure and launch Dockfra is the **interactive web wizard**:

```bash
make wizard          # Start wizard at http://localhost:5050
```

The wizard provides a **chat-based UI** with three panels:

| Panel | Description |
|---|---|
| 💬 **Chat** | Interactive step-by-step configuration assistant |
| ⚙️ **Processes** | Real-time container / launch progress |
| 📋 **Logs** | Streaming Docker Compose output |

### Wizard Features

- **Inline missing-field forms** — missing env vars appear as input fields immediately, no separate settings screen
- **Smart suggestions + clickable chips** — auto-detects git config, SSH keys, ARP devices, Docker networks, free ports; generates random secrets
- **DEVICE_IP auto-discovery** — priority chain: `devices/.env` → running container → ARP REACHABLE → ARP STALE (color-coded: 🟢/🟡/🟠)
- **Eye toggle** on all password/API-key fields
- **10 European languages** — selector in header, persisted to `localStorage` (pl, en, de, fr, es, it, pt, cs, ro, nl)
- **Settings sections** — ✅/🔴N status icons on each section button show completeness at a glance
- **Error analysis** — Docker Compose failures are parsed and presented as interactive solution buttons
- **Dashboard** at `http://localhost:5050/dashboard` — real-time container status + decision log

### Wizard API

| Endpoint | Method | Description |
|---|---|---|
| `/api/env` | GET | Read current config (secrets masked) |
| `/api/env` | POST | Update env vars |
| `/api/containers` | GET | Running container list |
| `/api/processes` | GET | Wizard-managed process list |
| `/api/history` | GET | Conversation + log history |
| `/api/events` | GET | Decision event log |

## Quick Start

### Option A — Web Wizard (recommended)

```bash
git clone <repo> dockfra && cd dockfra
make wizard          # Opens http://localhost:5050
                     # Fill in the form fields, click "Save & Launch"
```

### Option B — Makefile (manual)

```bash
git clone <repo> dockfra && cd dockfra

# 1. Initialize + start
make init                    # Generate keys, env files, docker network
make up                      # Start both stacks (app + management)

# 2. Setup GitHub credentials + LLM
pip install getv             # API key manager
getv set llm openrouter OPENROUTER_API_KEY=sk-or-v1-...
make setup-all               # GitHub keys + LLM + dev tools (one command)

# 3. Use
make ssh-developer           # SSH into developer workspace
make aider                   # Launch aider AI pair programming
make test-github             # Verify GitHub access
make test-llm                # Verify LLM connectivity
```

### Step-by-step (manual)

```bash
# 1. Initialize both stacks
make init-app
make init-mgmt

# 2. Configure LLM API key via getv
pip install getv
getv set llm openrouter OPENROUTER_API_KEY=sk-or-v1-your-key-here

# 3. Start
make up-app                  # App stack first
make up-mgmt                 # Management stack

# 4. Copy GitHub credentials to developer container
make setup-github            # Copies ~/.ssh/id_ed25519 + git config

# 5. Setup LLM (OpenRouter + LiteLLM + aider)
make setup-llm               # Injects OPENROUTER_API_KEY via getv
make setup-dev-tools         # Installs aider, configures Continue.dev

# 6. Login and work
make ssh-developer
aider-start                  # AI pair programming with Gemini Flash
litellm-start                # Start LiteLLM proxy for Continue.dev
```

### Production setup

```bash
# SERVER 1: Management
cd management && bash scripts/init.sh production
nano .env.production  # Set DEVELOPER_HOST, API keys
make up-prod

# SERVER 2: App
cd app && bash scripts/init.sh production
nano .env.production  # Set DB password, API keys, domain
# Copy management public keys to ssh-developer/keys/authorized_keys
make up-prod
```

## Makefile Reference

```bash
make help                    # Show all targets
```

| Target | Description |
|---|---|
| `make init` | Full initialization (keys, env, network) |
| `make up` / `make down` | Start / stop both stacks |
| `make build` | Build all Docker images |
| `make ps` | Show running containers |
| **GitHub + LLM** | |
| `make setup-github` | Copy host GitHub SSH keys to developer |
| `make setup-llm` | Configure LLM (OpenRouter via getv + LiteLLM) |
| `make setup-dev-tools` | Install aider, Continue.dev, Claude proxy |
| `make setup-all` | All three above in one command |
| **SSH Access** | |
| `make ssh-developer` | SSH into developer (port 2200) |
| `make ssh-manager` | SSH into manager (port 2202) |
| `make ssh-autopilot` | SSH into autopilot (port 2203) |
| `make ssh-monitor` | SSH into monitor (port 2201) |
| **LLM Tools** | |
| `make aider` | Start aider inside developer |
| `make litellm` | Start LiteLLM proxy (port 4000) |
| `make llm-ask Q="question"` | Quick LLM query |
| **getv** | |
| `make getv-list` | List getv profiles |
| `make getv-set-key KEY=sk-...` | Set OpenRouter API key |
| **Testing** | |
| `make test` | Full E2E test suite |
| `make test-github` | Test GitHub SSH from developer |
| `make test-llm` | Test LLM connectivity |
| `make test-ssh` | Test SSH ports |

## LLM-Powered Development (getv + OpenRouter)

### API Key Management with getv

[getv](https://github.com/wronai/getv) manages API keys securely in `~/.getv/`:

```bash
pip install getv

# Auto-detect from clipboard or set manually
getv set llm openrouter OPENROUTER_API_KEY=sk-or-v1-...

# Verify
getv list llm openrouter
getv get llm openrouter OPENROUTER_API_KEY

# Inject into container
make setup-llm               # Uses getv internally
```

The default model is **`google/gemini-3-flash-preview`** via OpenRouter. Override:
```bash
make setup-llm LLM_MODEL=anthropic/claude-sonnet-4
make aider LLM_MODEL=openai/gpt-4o
```

### LLM Dev Tools Inside ssh-developer

After `make setup-all`, these tools are available inside the developer container:

| Tool | Command | Description |
|---|---|---|
| **Aider** | `aider-start` | AI pair programming — edits files, commits |
| **LiteLLM** | `litellm-start` | OpenAI-compatible proxy on `:4000` |
| **Continue.dev** | VS Code extension | Config auto-loaded from `~/.continue/config.json` |
| **Claude Code** | `claude-proxy` | Routes through LiteLLM proxy |
| **Quick ask** | `llm-ask "question"` | One-shot LLM query |

### IDE Remote SSH (VS Code / Windsurf / Cursor)

Add to your **local** `~/.ssh/config`:

```
Host dockfra-developer
    HostName localhost
    Port 2200
    User developer
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
```

Then in your IDE:
1. **Cmd+Shift+P** → "Remote-SSH: Connect to Host" → `dockfra-developer`
2. Install **Continue** extension on the remote
3. Continue reads `~/.continue/config.json` (auto-configured by `make setup-dev-tools`)
4. Prompt: *"napraw DSI config"* — the LLM edits files directly inside the container

This works with **VS Code**, **Windsurf**, **Cursor**, and any VS Code fork with Remote-SSH.

## Ticket-Driven Workflow

```
Manager creates ticket ──► /shared/tickets/T-0001.json ──► Developer picks up
      │                            ▲                              │
      │ ticket-push T-0001         │ ticket-pull                  │ ticket-done
      ▼                            │                              ▼
  GitHub Issues ◄──────────────────┘                     status=closed
```

### From ssh-manager:
```bash
ticket-create "Feature X"               # Create ticket
ticket-create "Bug Y" --priority=high   # With priority
ticket-list                              # List all
ticket-push T-0001                       # Push to GitHub
ticket-pull                              # Pull from GitHub
plan "Add user authentication"           # LLM generates ticket plan
ask "How should I structure this?"       # Ask LLM
```

### From ssh-developer:
```bash
my-tickets                               # Show assigned tickets
ticket-work T-0001                       # Mark as in_progress
implement T-0001                         # AI-assisted implementation
review backend/app.py                    # AI code review
ask "How to fix this error?"             # Ask LLM
commit-push "Implemented auth"           # Git commit + push
ticket-done T-0001                       # Mark complete
```

## SSH Access Map

```
Port  │ Service        │ User       │ Role
──────┼────────────────┼────────────┼─────────────────────────
2202  │ ssh-manager    │ manager    │ Project management, tickets
2203  │ ssh-autopilot  │ autopilot  │ Autonomous orchestration
2200  │ ssh-developer  │ developer  │ Code, tests, git
2201  │ ssh-monitor    │ monitor    │ Deploy, health, monitoring
2222  │ ssh-frontend   │ deployer   │ Frontend bastion
2223  │ ssh-backend    │ deployer   │ Backend bastion
2224  │ ssh-rpi3       │ deployer   │ RPi3 deploy channel
```

## Network Isolation

```
mgmt-net ──────── ssh-manager, ssh-autopilot (+ ssh-net for reaching services)
dev-net ───────── ssh-developer (+ read-only: frontend-net, backend-net)
ssh-net ───────── ssh-monitor ↔ ssh-frontend ↔ ssh-backend ↔ ssh-rpi3
                  ssh-manager ↔ ssh-autopilot (management plane)
proxy-net ─────── traefik, all web services, vnc, monitor
backend-net ───── backend, mobile, db, redis, ssh-backend, developer(ro), monitor
frontend-net ──── frontend, ssh-frontend, developer(ro), monitor
rpi3-net ──────── ssh-rpi3, vnc-rpi3, monitor
desktop-net ───── desktop-app, ssh-rpi3
```

## Services (17 total)

### Wizard (host process)

| Service | Port | Description |
|---|---|---|
| **wizard** | **5050** | Setup wizard chat UI + REST API |
| wizard dashboard | 5050/dashboard | Container status + decision log |

### Management Stack

| Service | Port | Role | LLM |
|---|---|---|:---:|
| **ssh-manager** | **2202** | Ticket mgmt, config | ✓ |
| **ssh-autopilot** | **2203** | Autonomous orchestration | ✓ |
| **ssh-monitor** | **2201** | Deploy, health | ✓ |
| desktop | 6081 | noVNC + Chromium GUI | — |

### App Stack

| Service | Port | Role | LLM |
|---|---|---|:---:|
| traefik | 80, 443, 8080 | Reverse proxy | — |
| frontend | (int) | Web UI | — |
| backend | 8081 | REST API | — |
| mobile-backend | 8082 | Mobile API | — |
| desktop-app | 8083 | Build artifacts | — |
| db | 5432 | PostgreSQL | — |
| redis | 6379 | Cache | — |
| **ssh-developer** | **2200** | Code, tests, git | ✓ |

### Devices Stack

| Service | Port | Role |
|---|---|---|
| ssh-rpi3 | 2224 | RPi3 SSH channel |
| vnc-rpi3 | 6080 | Web VNC |

> RPi3 target IP configured via `DEVICE_IP` — auto-detected from ARP cache or `devices/.env`

## Autopilot Autonomous Mode

The autopilot daemon runs every `AUTOPILOT_INTERVAL` seconds and:
1. Gathers project state (tickets, service health, git status) via SSH
2. Sends state to LLM for decision-making
3. Executes recommended actions (create tickets, trigger deploys, alert)

```bash
# From ssh-autopilot:
pilot-status        # Daemon state + recent decisions
pilot-log           # Watch daemon log
pilot-run           # Trigger manual cycle
pilot-plan "goal"   # Generate plan via LLM
```

## Project Structure

```
dockfra/
├── init.sh                                 # One-command setup (both stacks)
├── README.md / LICENSE / CHANGELOG.md / TODO.md
├── project.functions.toon                  # Auto-generated function index (158 functions, 14 modules)
├── wizard/                                 # ══ SETUP WIZARD ══
│   ├── app.py                              # Flask+SocketIO backend (64 functions)
│   ├── run.sh                              # Start script
│   ├── requirements.txt                    # Flask, flask-socketio, gevent, psutil
│   ├── .env / .env.example                 # Wizard config (auto-created)
│   ├── templates/
│   │   ├── index.html                      # Chat UI shell (54 lines)
│   │   └── dashboard.html                  # Container status + logs dashboard
│   └── static/
│       ├── wizard.css                      # All styles (~120 lines)
│       └── wizard.js                       # All JS (20 functions, ~280 lines)
├── management/                             # ══ MANAGEMENT STACK ══
│   ├── docker-compose.yml                  # Local (3 services)
│   ├── docker-compose-production.yml       # Production
│   ├── .env.local / .env.production        # Auto-generated by init
│   ├── scripts/
│   │   ├── init.sh                         # Management setup
│   │   ├── generate-keys.sh               # ED25519 key generation
│   │   ├── setup-local.sh                 # Local env config
│   │   ├── setup-production.sh            # Production env config
│   │   └── sync-keys-to-developer.sh      # Copy pubkeys to app
│   ├── ssh-manager/                        # Manager role
│   │   ├── .env / Dockerfile / entrypoint.sh / motd
│   │   └── manager-scripts/               # 12 scripts
│   ├── ssh-autopilot/                      # Autopilot role
│   │   ├── .env / Dockerfile / entrypoint.sh / motd
│   │   ├── autopilot-daemon.sh            # Autonomous loop
│   │   └── autopilot-scripts/             # 4 scripts
│   ├── ssh-monitor/                        # Monitor role
│   │   ├── .env / Dockerfile / entrypoint.sh / motd
│   │   ├── monitor-daemon.sh              # Auto-poll + deploy
│   │   └── deploy-scripts/                # 8 scripts
│   ├── shared/                             # Shared volume (tickets, logs, lib)
│   │   └── lib/                            # llm_client.py, ticket_system.py
│   └── keys/                               # Auto-generated (gitignored)
│       ├── manager/id_ed25519{,.pub}
│       ├── autopilot/id_ed25519{,.pub}
│       └── monitor/id_ed25519{,.pub}
│
├── app/                                    # ══ APPLICATION STACK ══
│   ├── docker-compose.yml                  # Local (12 services)
│   ├── docker-compose-production.yml       # Production
│   ├── .env.local / .env.production        # Auto-generated by init
│   ├── scripts/
│   │   ├── init.sh                         # App setup
│   │   └── generate-developer-keys.sh     # Developer key generation
│   ├── ssh-developer/                      # Developer role
│   │   ├── .env / Dockerfile / entrypoint.sh / motd
│   │   ├── scripts/                       # 9 scripts
│   │   └── keys/                          # authorized_keys from management
│   ├── frontend/ backend/ mobile-backend/ desktop-app/
│   ├── ssh-rpi3/ vnc-rpi3/
├── shared/                                 # Shared libraries
│   └── lib/                                # llm_client.py, ticket_system.py
│
├── Makefile                                # Operational targets (make help)
├── scripts/                                # Host-side setup scripts
│   ├── setup-github-keys.sh              # Copy GitHub SSH keys to developer
│   ├── setup-llm.sh                      # Configure LLM via getv + OpenRouter
│   ├── setup-dev-tools.sh                # Install aider, Continue.dev, LiteLLM
│   └── inject-getv-env.sh               # Inject getv profile into container
├── tests/
│   └── run-tests.sh                      # E2E test suite (hybrid)
├── goal.yaml                               # Project goals
└── TODO/                                   # Architecture notes
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
