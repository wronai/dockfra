# SSH Role System

> Dockfra's role-based access control via isolated SSH containers.

## Overview

Each role runs in its own Docker container with:
- Dedicated SSH user and port
- Isolated filesystem and network access
- Role-specific scripts and commands
- Independent LLM configuration
- Auto-generated ED25519 SSH keys

## Roles

| Role | Container | User | Default Port | Purpose |
|---|---|---|---|---|
| **Developer** | `{prefix}-ssh-developer` | developer | 2200 | Code, tests, git, AI pair programming |
| **Manager** | `{prefix}-ssh-manager` | manager | 2202 | Tickets, config, project planning |
| **Monitor** | `{prefix}-ssh-monitor` | monitor | 2201 | Deploy, health checks, log analysis |
| **Autopilot** | `{prefix}-ssh-autopilot` | autopilot | 2203 | Autonomous LLM-driven orchestration |

## Capability Matrix

| Capability | Manager | Autopilot | Developer | Monitor |
|---|:---:|:---:|:---:|:---:|
| Create/manage tickets | ✓ | ✓ | — | — |
| Push/pull tickets to GitHub | ✓ | — | — | — |
| Configure LLM on services | ✓ | — | — | — |
| SSH to all role services | ✓ | ✓ | — | — |
| Work on assigned tickets | — | — | ✓ | — |
| Edit code / git push | — | — | ✓ | — |
| Run local tests | — | — | ✓ | — |
| LLM code assistance | — | — | ✓ | — |
| Deploy to production | — | — | **✗** | ✓ |
| Health monitoring daemon | — | — | — | ✓ |
| LLM log analysis | — | — | — | ✓ |
| Autonomous orchestration | — | ✓ | — | — |
| Docker socket access | — | — | **✗** | ✓ |

## Architecture

### Shared Base Image

All SSH roles use a shared base image (`{prefix}-ssh-base`) built from `shared/Dockerfile.ssh-base`:

```
shared/Dockerfile.ssh-base          ← Universal base (openssh, Python, pip)
  │
  ├─ app/ssh-developer/Dockerfile   ← Adds: developer user, git, dev tools
  ├─ management/ssh-manager/Dockerfile    ← Adds: manager user
  ├─ management/ssh-monitor/Dockerfile    ← Adds: monitor user, iproute2
  └─ management/ssh-autopilot/Dockerfile  ← Adds: autopilot user
```

### Shared Init Script

Each container sources `shared/ssh-base-init.sh` in its entrypoint:

```bash
#!/bin/bash
source /usr/local/lib/ssh-base-init.sh   # SSH keys, bashrc, PATH
# ... role-specific setup follows
```

The base init handles: SSH host keys, user SSH keys, `.bashrc` setup, PATH configuration.

### Script Discovery

Scripts are discovered from `{role-dir}/scripts/` and `Makefile` targets:

```
app/ssh-developer/
├── Makefile              ← Targets become wizard commands
├── scripts/
│   ├── ask.sh            ← LLM query
│   ├── implement.sh      ← AI-assisted implementation
│   ├── review.sh         ← AI code review
│   ├── commit-push.sh    ← Git commit + push
│   └── ...
├── entrypoint.sh         ← Container startup
└── Dockerfile
```

The wizard reads Makefiles to build command grids:

```python
# discover.py auto-discovers:
_SSH_ROLES = {
    "developer": {
        "container": "dockfra-ssh-developer",
        "user": "developer",
        "port": "2200",
        "commands": ["ask", "implement", "review", "commit-push", ...],
        "cmd_meta": {"ask": {"params": ["Q"], "tty": False}, ...}
    }
}
```

## Command Examples

### Developer

```bash
ssh developer@localhost -p 2200

# Inside container:
ask "How to fix this error?"          # LLM query
implement T-0001                       # AI-assisted ticket implementation
review backend/app.py                  # AI code review
commit-push "Implemented feature X"    # Git commit + push
my-tickets                             # Show assigned tickets
ticket-work T-0001                     # Mark ticket in progress
ticket-done T-0001                     # Mark ticket complete
aider-start                            # AI pair programming (aider)
litellm-start                          # Start LLM proxy
```

### Manager

```bash
ssh manager@localhost -p 2202

ticket-create "Feature X"             # Create ticket
ticket-list                            # List all tickets
ticket-push T-0001                     # Push to GitHub Issues
ticket-pull                            # Pull from GitHub Issues
plan "Add user authentication"         # LLM generates ticket plan
config-developer                       # View/update developer config
config-show all                        # View all service configs
```

### Monitor

```bash
ssh monitor@localhost -p 2201

deploy latest                          # Deploy latest to production
health-check                           # Run health checks
service-status                         # All service statuses
log-analyze backend                    # LLM log analysis
```

### Autopilot

```bash
ssh autopilot@localhost -p 2203

pilot-status                           # Daemon state + recent decisions
pilot-log                              # Watch daemon log
pilot-run                              # Trigger manual decision cycle
pilot-plan "Scale frontend"            # LLM generates action plan
```

## Virtual Developer Role

When `app/` hasn't been cloned yet but `GIT_REPO_URL` is configured, Dockfra shows a **virtual developer** role in the wizard. Clicking it offers to clone the repository and launch the app stack.

## LLM Configuration per Role

Each role has independent LLM settings:

```
app/ssh-developer/.env         → OPENROUTER_API_KEY, LLM_MODEL
management/ssh-manager/.env    → OPENROUTER_API_KEY, LLM_MODEL
management/ssh-monitor/.env    → OPENROUTER_API_KEY, LLM_MODEL
management/ssh-autopilot/.env  → OPENROUTER_API_KEY, LLM_MODEL
```

Configure from the manager:
```bash
# From ssh-manager:
config-developer               # View/update developer LLM config
config-monitor                 # View/update monitor LLM config
```

## Network Isolation

```
mgmt-net ──────── ssh-manager, ssh-autopilot
dev-net ───────── ssh-developer (+ read-only: frontend-net, backend-net)
ssh-net ───────── all ssh-* roles (management plane)
proxy-net ─────── traefik, web services, monitor
backend-net ───── backend, db, redis, developer(ro), monitor
frontend-net ──── frontend, developer(ro), monitor
```

## See Also

- [Architecture](ARCHITECTURE.md) — system overview
- [Configuration](CONFIGURATION.md) — env vars and dockfra.yaml
- [Getting Started](GETTING-STARTED.md) — quickstart guide
