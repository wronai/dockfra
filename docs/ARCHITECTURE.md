# Dockfra Architecture

> Detailed technical architecture of the Dockfra multi-agent Docker infrastructure system.

## Overview

Dockfra is a **generic Docker project manager** with an interactive web wizard, SSH-based role separation, LLM integration, and autonomous orchestration. It can manage **any** Docker Compose project — just point it at a directory containing `docker-compose.yml` files.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DOCKFRA SYSTEM                               │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │  Web Wizard   │   │   CLI        │   │  Makefile targets      │  │
│  │  :5050        │   │  dockfra-cli │   │  make up/down/init     │  │
│  └──────┬───────┘   └──────┬───────┘   └───────────┬────────────┘  │
│         │                  │                        │               │
│         ▼                  ▼                        ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    dockfra/ Python package                   │   │
│  │  core.py ─── app.py ─── steps.py ─── fixes.py ─── discover │   │
│  │  (1012 lines) (652)    (645)       (530)        (345)       │   │
│  │  + cli.py (438) + llm_client.py (108) + __main__.py (64)   │   │
│  │  Total: 3807 lines, 135 functions, 8 modules                │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                   │
│         ▼                   ▼                   ▼                   │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────────┐         │
│  │ Auto-       │   │ Docker       │   │ dockfra.yaml     │         │
│  │ discovered  │   │ Compose      │   │ (optional        │         │
│  │ stacks/     │   │ engine       │   │  project config) │         │
│  └────────────┘   └──────────────┘   └──────────────────┘         │
└─────────────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### `core.py` — Foundation (1012 lines, 38 functions)

The central module. Everything else imports `from .core import *`.

| Section | What it does |
|---|---|
| **Project naming** | `PROJECT` dict, `cname()`, `short_name()` — configurable via `DOCKFRA_PREFIX` |
| **Stack discovery** | `_discover_stacks()` → `STACKS` dict — scans ROOT for `docker-compose.yml` |
| **Config loading** | `_load_project_config()` → reads optional `dockfra.yaml` |
| **Env var discovery** | `_parse_compose_env_vars()` → extracts `${VAR:-default}` from compose files |
| **ENV_SCHEMA** | `_build_env_schema()` — merges core + discovered + yaml overrides |
| **Field metadata** | `_FIELD_META` — descriptions, autodetect flags for known vars |
| **State management** | `_state`, `_ENV_TO_STATE` (auto-generated), `reset_state()` |
| **Flask + SocketIO** | App initialization, CORS, gevent/threading mode |
| **UI helpers** | `msg()`, `buttons()`, `text_input()`, `select()`, `progress()`, etc. |
| **Docker utils** | `docker_ps()`, `run_cmd()`, `_docker_client()`, `_docker_logs()` |
| **Health patterns** | `_HEALTH_PATTERNS` — regex patterns for Docker error detection |
| **LLM** | `_llm_chat()`, `_llm_config()` — OpenRouter integration |
| **Network utils** | ARP scan, subnet ping sweep, interface detection |

### `app.py` — Web Server & API (652 lines, 22 functions)

Flask routes and SocketIO event handlers.

| Component | Description |
|---|---|
| `on_action` | Main SocketIO dispatcher — routes user actions to step functions |
| `_dispatch()` | Shared dispatch logic for both SocketIO and REST API |
| `/api/env` | GET/POST env vars (secrets masked) |
| `/api/containers` | Running Docker containers |
| `/api/processes` | Wizard-managed process list |
| `/api/detect/<key>` | Auto-detect env var values (git repo, branch, app version) |
| `/api/ssh-options` | SSH role options (tickets, files, branches) |
| `/api/action` | REST API for wizard actions (non-WebSocket clients) |

### `steps.py` — Wizard Steps (645 lines, 22 functions)

The wizard flow logic.

| Step | Function | Description |
|---|---|---|
| Welcome | `step_welcome()` | Initial screen, auto-detect config |
| Status | `step_status()` | Show running containers |
| Settings | `step_settings()` | ENV editor by group |
| Launch | `step_do_launch()` | Build & start Docker stacks |
| Deploy | `step_deploy_device()` | Deploy to IoT/RPi devices |
| Preflight | `step_preflight_fill()` | Check required vars before launch |
| Post-launch | (inline) | SSH role buttons, health checks |

### `fixes.py` — Repair Functions (530 lines, 15 functions)

Automated fixes for common Docker problems.

| Fix | Description |
|---|---|
| `step_fix_container()` | Restart/rebuild individual container |
| `fix_network_overlap()` | Remove conflicting Docker networks |
| `fix_acme_storage()` | Configure Let's Encrypt ACME |
| `fix_readonly_volume()` | Fix volume permission issues |
| `fix_docker_perms()` | Fix Docker socket permissions |
| `fix_vnc_port()` | Change conflicting VNC port |
| `show_missing_env()` | Diagnose missing env vars per stack |

### `discover.py` — Role & Command Discovery (345 lines, 9 functions)

Auto-discovers SSH roles and their available commands from Makefiles.

| Function | Description |
|---|---|
| `_discover_ssh_roles()` | Scan stack dirs for `ssh-*` subdirs with Makefiles |
| `_get_role()` | Get role data with fallback stubs |
| `_step_ssh_info()` | Show role info + command grid |
| `step_ssh_console()` | Interactive SSH console |
| `run_ssh_cmd()` | Execute command in container |
| `_refresh_ssh_roles()` | Re-scan roles (after clone/config change) |

### `cli.py` — Command-Line Interface (438 lines, 21 functions)

Click-based CLI for non-wizard usage.

```bash
dockfra status          # Container status
dockfra env             # Show/edit env vars
dockfra launch          # Launch stacks
dockfra ssh developer   # SSH into role
```

### `llm_client.py` — LLM Integration (108 lines, 4 functions)

OpenRouter API client shared between wizard and CLI.

## Data Flow

### 1. Configuration Discovery (startup)

```
ROOT directory
  │
  ├─ _discover_stacks() ──► STACKS = {app: Path, management: Path, devices: Path}
  │
  ├─ _load_project_config() ──► _PROJECT_CONFIG from dockfra.yaml (optional)
  │
  ├─ _parse_compose_env_vars() ──► _COMPOSE_VARS = {VAR: {default, stack, type}}
  │                                  (55 vars parsed from docker-compose files)
  │
  └─ _build_env_schema() ──► ENV_SCHEMA = [core entries + discovered + yaml overrides]
                               (62 total entries, auto-grouped by stack)
```

### 2. Wizard Flow

```
Browser (wizard.js)
  │ WebSocket
  ▼
on_action(value, form)
  │
  ├─ "welcome"      → step_welcome()      → detect_config() + suggestions
  ├─ "settings"     → step_settings()      → ENV_SCHEMA grouped UI
  ├─ "do_launch"    → step_do_launch()     → preflight → clone? → docker compose up
  ├─ "ssh_info::*"  → _step_ssh_info()     → role commands from Makefile
  ├─ "fix_*"        → fixes module         → automated repair
  └─ free text      → _llm_chat()          → AI assistance
```

### 3. Stack Launch Sequence

```
step_do_launch(form)
  │
  ├─ 1. Resolve target stacks from STACKS dict
  ├─ 2. If app/ missing + GIT_REPO_URL set → git clone
  ├─ 3. Preflight: check required env vars per stack
  ├─ 4. docker network create {prefix}-shared
  ├─ 5. Build ssh-base image (if ssh-* dirs detected)
  ├─ 6. docker compose up -d --build (per stack)
  ├─ 7. Wait 8s, health check all containers
  └─ 8. Show post-launch UI (SSH roles, fix buttons)
```

## Naming Convention

All Docker resources use a configurable prefix (default: `dockfra`):

```
DOCKFRA_PREFIX=myapp  →  myapp-shared (network)
                         myapp-ssh-base (image)
                         myapp-traefik (container)
                         myapp-ssh-developer (container)
```

Functions: `cname("traefik")` → `"dockfra-traefik"`, `short_name("dockfra-traefik")` → `"traefik"`

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask, Flask-SocketIO |
| Async | gevent (preferred) or threading fallback |
| Frontend | Vanilla JS, CSS (no framework) |
| Containers | Docker, Docker Compose |
| SSH | OpenSSH in containers, ED25519 keys |
| LLM | OpenRouter API (multi-model) |
| CLI | Click framework |
| Testing | Bash test suite (70 tests) |

## See Also

- [Getting Started](GETTING-STARTED.md) — quickstart for any Docker project
- [Configuration](CONFIGURATION.md) — dockfra.yaml, ENV_SCHEMA, auto-discovery
- [SSH Roles](SSH-ROLES.md) — role separation and command system
- [Wizard API](WIZARD-API.md) — REST + WebSocket API reference
- [Comparisons](../comparisons/README.md) — vs other multi-agent Docker systems
