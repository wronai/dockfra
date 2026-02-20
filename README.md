# Infra-Deploy: LLM-Powered Role-Based Infrastructure

Multi-service Docker infrastructure with strict role separation, LLM integration via OpenRouter,
ticket-driven workflows, and autonomous orchestration.

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  YOU (Human)                                                            │
  │  ssh manager@localhost -p 2202   │   ssh autopilot@localhost -p 2203    │
  └────────┬─────────────────────────┴──────────┬───────────────────────────┘
           │                                    │
           ▼                                    ▼
  ┌──────────────────┐              ┌────────────────────┐
  │   SSH-MANAGER    │   tickets    │   SSH-AUTOPILOT    │
  │   :2202          │◄────────────►│   :2203            │
  │                  │              │                    │
  │ • Create tickets │   SSH cmds   │ • LLM decisions    │
  │ • Config LLM     ├─────────────►│ • Auto-orchestrate │
  │ • Push to GitHub │              │ • Monitor cycles   │
  │ • Update .env    │              │ • Create tickets   │
  │   via SSH        │              │   autonomously     │
  └───────┬──────────┘              └────────┬───────────┘
          │ SSH config updates                │ SSH orchestration
          │ + ticket creation                 │ + health monitoring
          ▼                                   ▼
  ┌──────────────────┐              ┌────────────────────┐
  │  SSH-DEVELOPER   │   tickets    │   SSH-MONITOR      │
  │  :2200           │◄────────────►│   :2201            │
  │                  │  (shared     │                    │
  │ • Work on tickets│   volume)    │ • Deploy via SSH   │
  │ • LLM code help  │              │ • Health checks    │
  │ • Git commit/push│              │ • LLM log analysis │
  │ • Run tests      │              │ • Auto-poll git    │
  └──────────────────┘              └────────┬───────────┘
                                             │ SSH deploy
                                    ┌────────┼────────┐
                                    ▼        ▼        ▼
                              ssh-front  ssh-back  ssh-rpi3
                              (:2222)    (:2223)   (:2224)
                                 │          │         │
                              frontend   backend    vnc-rpi3
                              mobile     db/redis   desktop
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
ssh-developer/.env    → LLM for code reviews, implementation, debugging
ssh-monitor/.env      → LLM for log analysis, deployment decisions
ssh-manager/.env      → LLM for ticket planning, project management
ssh-autopilot/.env    → LLM for autonomous orchestration decisions
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

## Quick Start

```bash
# 1. Setup
git clone <repo> infra-deploy && cd infra-deploy
chmod +x scripts/*.sh
./scripts/setup.sh local

# 2. Configure LLM (edit API keys)
nano ssh-developer/.env      # Set OPENROUTER_API_KEY
nano ssh-monitor/.env        # Set OPENROUTER_API_KEY
nano ssh-manager/.env        # Set OPENROUTER_API_KEY
nano ssh-autopilot/.env      # Set OPENROUTER_API_KEY

# 3. Build & start
docker compose build && docker compose up -d

# 4. Login as Manager
ssh manager@localhost -p 2202

# 5. Create tickets for developer
ticket-create "Add user auth" --priority=high --desc="Implement JWT auth"
ticket-create "Write tests" --priority=normal

# 6. Check developer workspace
ssh developer@localhost -p 2200
my-tickets                     # See assigned tickets
implement T-0001               # AI-assisted implementation
ticket-done T-0001

# 7. Run E2E tests
./scripts/run-tests.sh
```

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

## Services (15 total)

| Service | Port | Role | LLM |
|---|---|---|:---:|
| traefik | 80, 443, 8080 | Reverse proxy | — |
| frontend | (int) | Web UI | — |
| backend | 8081 | REST API | — |
| mobile-backend | 8082 | Mobile API | — |
| desktop-app | 8083 | Build artifacts | — |
| db | 5432 | PostgreSQL | — |
| redis | 6379 | Cache | — |
| **ssh-manager** | **2202** | **Ticket mgmt, config** | **✓** |
| **ssh-autopilot** | **2203** | **Autonomous orchestration** | **✓** |
| **ssh-developer** | **2200** | **Code, tests, git** | **✓** |
| **ssh-monitor** | **2201** | **Deploy, health** | **✓** |
| ssh-frontend | 2222 | Frontend bastion | — |
| ssh-backend | 2223 | Backend bastion | — |
| ssh-rpi3 | 2224 | RPi3 channel | — |
| vnc-rpi3 | 6080 | Web VNC | — |

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
infra-deploy/
├── .env / .env.local / .env.production    # Global config
├── docker-compose.yml                      # 15 services
├── shared/
│   └── lib/
│       ├── llm_client.py                   # OpenRouter LLM client
│       └── ticket_system.py                # Local + GitHub tickets
├── ssh-manager/                            # Manager role
│   ├── .env                                # Manager LLM config
│   ├── Dockerfile / entrypoint.sh / motd
│   └── manager-scripts/                    # 12 scripts
├── ssh-autopilot/                          # Autopilot role
│   ├── .env                                # Autopilot LLM config
│   ├── Dockerfile / entrypoint.sh / motd
│   ├── autopilot-daemon.sh                 # Autonomous loop
│   └── autopilot-scripts/                  # 4 scripts
├── ssh-developer/                          # Developer role
│   ├── .env                                # Developer LLM config
│   ├── Dockerfile / entrypoint.sh / motd
│   └── dev-scripts/                        # 9 scripts
├── ssh-monitor/                            # Monitor role (ex-agent)
│   ├── .env                                # Monitor LLM config
│   ├── Dockerfile / entrypoint.sh / motd
│   ├── monitor-daemon.sh                   # Auto-poll + deploy
│   └── deploy-scripts/                     # 8 scripts
├── frontend/ backend/ mobile-backend/ desktop-app/
├── ssh-rpi3/ vnc-rpi3/
├── scripts/
│   ├── setup.sh
│   └── run-tests.sh                        # E2E (33 tests)
└── keys/                                   # SSH keys (gitignored)
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Author

Created by **Tom Sapletta** - [tom@sapletta.com](mailto:tom@sapletta.com)
