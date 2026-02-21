# Dockfra Architecture

> Detailed technical architecture of the Dockfra multi-agent Docker infrastructure system.

## Overview

Dockfra is a **generic Docker project manager** with an interactive web wizard, SSH-based role separation, LLM integration, and autonomous orchestration. It can manage **any** Docker Compose project — just point it at a directory containing `docker-compose.yml` files.

```
┌────────────────────────────────────────────────────────────────────┐
│                        DOCKFRA SYSTEM (v1.0.41)                    │
│                                                                    │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │  Web Wizard  │   │  CLI (14 cmd)│   │  Makefile targets      │  │
│  │  :5050       │   │  dockfra cli │   │  make up/down/init     │  │
│  └──────┬───────┘   └──────┬───────┘   └───────────┬────────────┘  │
│         │                  │                       │               │
│         ▼                  ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   dockfra/ Python package                   │   │
│  │  core.py ── app.py ── steps.py ── engines.py ── pipeline.py │   │
│  │  cli.py ── fixes.py ── discover.py ── tickets.py            │   │
│  │  llm_client.py ── __main__.py                               │   │
│  │  10 modules, 150+ functions                                 │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                      │
│     ┌───────────────────────┼───────────────────────┐              │
│     ▼                       ▼                       ▼              │
│  ┌───────────┐   ┌────────────────┐   ┌──────────────────────┐     │
│  │ 3 Docker  │   │ 5 Dev Engines  │   │ 4 SSH Roles          │     │
│  │ stacks    │   │ (Aider, Claude │   │ (developer, manager, │     │
│  │ (15 cont.)│   │  Code, etc.)   │   │  monitor, autopilot) │     │
│  └───────────┘   └────────────────┘   └──────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### `core.py` — Foundation

The central module. Everything else imports `from .core import *`.

| Section | What it does |
|---|---|
| **Project naming** | `PROJECT` dict, `cname()`, `short_name()` — configurable via `DOCKFRA_PREFIX` |
| **Stack discovery** | `_discover_stacks()` → `STACKS` dict — scans ROOT for `docker-compose.yml` |
| **Config loading** | `_load_project_config()` → reads optional `dockfra.yaml` |
| **Env var discovery** | `_parse_compose_env_vars()` → extracts `${VAR:-default}` from compose files |
| **ENV_SCHEMA** | `_build_env_schema()` — merges core + discovered + yaml overrides |
| **State management** | `_state`, `_ENV_TO_STATE` (auto-generated), `reset_state()` |
| **Flask + SocketIO** | App initialization, CORS, gevent/threading mode |
| **UI helpers** | `msg()`, `buttons()`, `text_input()`, `select()`, `progress()`, etc. |
| **Docker utils** | `docker_ps()`, `run_cmd()`, `_docker_client()`, `_docker_logs()` |
| **MOTD filtering** | `_strip_motd_line()` — strips box-drawing banners from container output |
| **LLM** | `_llm_chat()`, `_llm_config()` — OpenRouter integration |
| **Network utils** | ARP scan, subnet ping sweep, interface detection |

### `app.py` — Web Server & API (20+ routes)

Flask routes and SocketIO event handlers.

| Component | Description |
|---|---|
| `on_action` | Main SocketIO dispatcher — routes user actions to step functions |
| `/api/env` | GET/POST env vars (secrets masked) |
| `/api/containers` | Running Docker containers |
| `/api/health` | Container health + error findings |
| `/api/tickets` | Ticket list (JSON) |
| `/api/ticket-diff/<id>` | Git commits + unified diff for ticket |
| `/api/stats` | Project statistics (git, tickets, containers) |
| `/api/developer-health` | SSH developer container health |
| `/api/engine-status` | Dev engine test results |
| `/api/developer-logs` | SSH developer container logs |
| `/api/ssh-options` | SSH role options (tickets, files, branches) |
| `/api/action` | REST API for wizard actions |

### `engines.py` — Dev Engine Registry (5 engines)

<a name="dev-engines"></a>

Manages detection, testing, and invocation of autonomous coding tools inside `ssh-developer`.

| Engine | ID | Detection | Test | Key required |
|---|---|---|---|---|
| **Built-in LLM** | `built_in` | `llm_client.py` importable | API call `chat('Say OK')` | `OPENROUTER_API_KEY` |
| **Aider** | `aider` | `command -v aider` | `aider --version` + dry run | `OPENROUTER_API_KEY` |
| **Claude Code** | `claude_code` | `command -v claude` | `claude --version` | `ANTHROPIC_API_KEY` |
| **OpenCode** | `opencode` | `command -v opencode` | `opencode --version` | `OPENROUTER_API_KEY` |
| **MCP SSH Manager** | `mcp_ssh` | `npm list -g` check | Node require test | — |

Key functions: `discover_engines()`, `test_engine()`, `test_all_engines()`, `select_first_working()`, `get_implement_cmd()`, `get_preferred_engine()`, `set_preferred_engine()`.

### `steps.py` — Wizard Steps

| Step | Function | Description |
|---|---|---|
| Welcome | `step_welcome()` | Initial screen, auto-detect config |
| Status | `step_status()` | Show running containers |
| Settings | `step_settings()` | ENV editor by group |
| Launch | `step_do_launch()` | Build & start Docker stacks |
| Deploy | `step_deploy_device()` | Deploy to IoT/RPi devices |
| Preflight | `step_preflight_fill()` | Check required vars before launch |

### `cli.py` — Command-Line Interface (14 commands)

REST client that talks to the wizard HTTP API.

| Command | Function | Description |
|---|---|---|
| `status` | `cmd_status` | Container health overview |
| `tickets` | `cmd_tickets` | List tickets with status/priority icons |
| `diff <id>` | `cmd_diff` | Show ticket diff + commits |
| `pipeline <id>` | `cmd_pipeline` | Run full pipeline for ticket |
| `engines` | `cmd_engines` | LLM engine status with preferred marker |
| `dev-health` | `cmd_dev_health` | Developer container health checks |
| `dev-logs [N]` | `cmd_dev_logs` | Developer container logs |
| `test` | `cmd_test` | Full system self-test (7 checks) |
| `doctor` | `cmd_doctor` | Diagnose issues, suggest fixes |
| `logs [N]` | `cmd_logs` | Wizard log tail |
| `launch` | `cmd_launch` | Launch stacks |
| `ask <text>` | `cmd_ask` | LLM query |
| `action <val>` | `cmd_action` | Raw wizard action |
| `--tui` | `run_tui` | Three-panel curses TUI |

Also includes: interactive REPL with readline history, tab completion.

### `fixes.py` — Repair Functions

| Fix | Description |
|---|---|
| `step_fix_container()` | Restart/rebuild individual container |
| `fix_network_overlap()` | Remove conflicting Docker networks |
| `fix_acme_storage()` | Configure Let's Encrypt ACME |
| `fix_readonly_volume()` | Fix volume permission issues |
| `fix_docker_perms()` | Fix Docker socket permissions |
| `show_missing_env()` | Diagnose missing env vars per stack |

### `discover.py` — Role & Command Discovery

Auto-discovers SSH roles and their available commands from container scripts.

### `llm_client.py` — LLM Integration

OpenRouter API client shared between wizard, CLI, and container scripts.

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
  │
  └─ _build_env_schema() ──► ENV_SCHEMA = [core entries + discovered + yaml overrides]
                               (62 total entries, auto-grouped by stack)
```

### 2. Ticket Pipeline

```
Manager creates T-0001 ──► /shared/tickets/T-0001.json
      │
      ▼
Developer picks up ──► select_first_working() → engine_id
      │
      ▼
get_implement_cmd(engine_id, T-0001) → shell command
      │
      ▼
_run_in_container(ssh-developer, developer, cmd)
      │
      ├─ Aider: aider --message "Implement: ..." --auto-commits
      ├─ Claude Code: claude --print "Implement: ..."
      ├─ OpenCode: opencode chat "Implement: ..."
      └─ Built-in: /home/developer/scripts/implement.sh T-0001
      │
      ▼
Git commit in /repo → ticket status = review
      │
      ▼
ssh-monitor: deploy to devices/ → verify HTTP /health
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
  └─ 8. Show post-launch UI (SSH roles, fix buttons, engine selector)
```

### 4. Autopilot ↔ SSH Role Communication

```
ssh-autopilot
  ├─ SSH → ssh-developer (code changes, implement tickets)
  ├─ SSH → ssh-manager (ticket status, planning)
  └─ SSH → ssh-monitor (deploy, verify health)
      └─ SSH → ssh-rpi3 (device deployment)
          └─ HTTP → web-rpi3 (/health, /api/status)
```

## Device Emulation (`devices/`)

The `devices/` stack emulates production machines for testing:

| Service | Port | Role |
|---|---|---|
| `ssh-rpi3` | `:2224` | SSH deploy channel (deployer user, /home/deployer/apps) |
| `web-rpi3` | `:8090` | Nginx HTTP — `/health` returns JSON, serves deployed app |
| `vnc-rpi3` | `:6082` | Web VNC access for visual inspection |

Shared volumes: `rpi3-www` (web content), `rpi3-apps` (artifacts). Deploy via SSH → artifacts land in shared volume → nginx serves them.

## Naming Convention

All Docker resources use a configurable prefix (default: `dockfra`):

```
DOCKFRA_PREFIX=myapp  →  myapp-shared (network)
                         myapp-ssh-base (image)
                         myapp-traefik (container)
```

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask, Flask-SocketIO |
| Async | gevent (preferred) or threading fallback |
| Frontend | Vanilla JS, CSS (no framework) |
| Containers | Docker, Docker Compose (15 containers) |
| SSH | OpenSSH, ED25519 keys, 4 roles |
| Dev engines | Aider, Claude Code, OpenCode, Built-in LLM, MCP SSH |
| LLM | OpenRouter API (multi-model) |
| CLI | argparse + urllib REST client, curses TUI |
| Testing | pytest (36 tests) |
| Devices | nginx, SSH, VNC (RPi3 emulation) |

## See Also

- [Getting Started](GETTING-STARTED.md) — quickstart for any Docker project
- [Configuration](CONFIGURATION.md) — dockfra.yaml, ENV_SCHEMA, auto-discovery
- [SSH Roles](SSH-ROLES.md) — role separation and command system
- [Wizard API](WIZARD-API.md) — REST + WebSocket API reference
- [Comparisons](../comparisons/README.md) — vs other multi-agent Docker systems
- [TODO](../TODO.md) — current roadmap
- [Changelog](../CHANGELOG.md) — release history
