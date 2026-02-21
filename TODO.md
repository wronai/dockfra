# Dockfra TODO

_Last updated: 2026-02-21 — v1.0.41, 10 modules, 150+ functions, 15 containers, 5 engines_

---

## ✅ Completed

### Core & Architecture
- [x] Python package: `dockfra/` — core, app, steps, engines, pipeline, tickets, fixes, discover, cli, llm_client
- [x] Central `PROJECT` config with `cname()`, `short_name()` — configurable via `DOCKFRA_PREFIX`
- [x] Auto-discover stacks from subdirectories with `docker-compose.yml` (`STACKS` dict)
- [x] Auto-discover env vars from compose files — parses `${VAR:-default}` patterns (55+ vars)
- [x] `_build_env_schema()` — merges core + discovered + dockfra.yaml overrides (62 entries)
- [x] `dockfra.yaml` optional project config — override labels, types, groups, descriptions
- [x] Shared SSH base image (`shared/Dockerfile.ssh-base`) + per-role thin Dockerfiles
- [x] MOTD box-drawing filter in `run_cmd()` — prevents MOTD leaking into pipeline output

### Dev Engines (`engines.py`)
- [x] Engine registry: 5 engines (Built-in LLM, Aider, Claude Code, OpenCode, MCP SSH Manager)
- [x] Auto-detect + test each engine in container (`discover_engines()`, `test_all_engines()`)
- [x] Auto-select first working engine (`select_first_working()`)
- [x] Persistent engine preference (`get/set_preferred_engine()`)
- [x] Engine-specific implement commands (`get_implement_cmd()`)
- [x] PATH fix for pip-installed tools (`/home/{user}/.local/bin`)

### CLI (`cli.py` — 14 commands)
- [x] `test` — full system self-test (wizard, containers, developer, engines, APIs)
- [x] `doctor` — diagnose issues, suggest fixes
- [x] `tickets` — list tickets with status/priority
- [x] `diff <T-XXXX>` — show ticket diff + commits
- [x] `pipeline <T-XXXX>` — run pipeline for ticket
- [x] `engines` — LLM engine status
- [x] `dev-health` / `dev-logs` — developer container diagnostics
- [x] `status`, `logs`, `launch`, `ask`, `action` — core commands
- [x] `--tui` — three-panel curses TUI (chat, processes, logs)
- [x] Interactive REPL with readline history, tab completion

### Wizard & API
- [x] Web setup wizard — Flask + SocketIO chat UI
- [x] 20+ API endpoints: `/api/tickets`, `/api/ticket-diff`, `/api/stats`, `/api/developer-health`, `/api/engine-status`, `/api/developer-logs`
- [x] Diff view with commit history + unified diff
- [x] Change count badges on ticket cards
- [x] Clipboard copy limit: 45000 chars
- [x] Dashboard at `/dashboard` — real-time container status + decision log
- [x] 10 European languages (pl, en, de, fr, es, it, pt, cs, ro, nl)

### Infrastructure
- [x] Ticket-driven workflow with GitHub Issues sync
- [x] Autopilot SSH communication with all roles (developer, manager, monitor)
- [x] SSH role isolation (4 roles × ED25519 keys)
- [x] Auto-repair: container restart, network overlap, ACME, volume perms
- [x] shared/lib/ — llm_client.py, ticket_system.py, logger.py

### Devices (`devices/`)
- [x] RPi3 emulation: SSH deploy channel (ssh-rpi3 :2224)
- [x] HTTP/HTTPS web server (web-rpi3 :8090) with `/health` + `/api/status`
- [x] Shared volumes: `rpi3-www` (web), `rpi3-apps` (artifacts)
- [x] Deploy helper scripts: `push-to-rpi3.sh`, `run-on-rpi3.sh`, `deploy-web.sh`
- [x] VNC access (vnc-rpi3 :6082)

### Documentation
- [x] README.md — badges, engines, CLI, architecture diagram, device emulation
- [x] docs/ARCHITECTURE.md — engines, pipeline, CLI, device emulation, autopilot flow
- [x] docs/CONFIGURATION.md, GETTING-STARTED.md, SSH-ROLES.md, WIZARD-API.md
- [x] comparisons/ — vs Kamal, Coolify, Portainer, CrewAI/AutoGen, OpenDevin/Aider
- [x] 36/36 pytest tests passing

---

## In Progress

- [ ] Post-launch plugin system — config-driven UI from `dockfra.yaml` (see `docs/PLAN-post-launch-plugins.md`)
- [ ] Full autonomous pipeline: autopilot → create ticket → developer implements → monitor deploys → verify

---

## Pending

### Core
- [ ] `dockfra.yaml` `post_launch` hooks — config-driven post-launch buttons and actions
- [ ] `dockfra.yaml` `fixes` section — project-specific fix plugins
- [ ] i18n for all Python-side messages (currently Polish; `lang:` from dockfra.yaml)
- [ ] Persistent `_state` across restarts (save to `dockfra/.env` on shutdown)

### Engines
- [ ] OpenCode Go binary install automation (currently best-effort in Dockerfile)
- [ ] MCP SSH Manager npm package validation (package name TBD)
- [ ] Continue.dev integration (VS Code plugin, remote config via SSH)
- [ ] Engine benchmark — compare implementation speed and quality per engine

### Devices Stack
- [ ] HTTPS (self-signed cert) on web-rpi3 for TLS testing
- [ ] Multiple device types (rpi4, jetson, generic-linux)
- [ ] Auto-ping sweep when ARP cache is empty
- [ ] SSH key auto-install to target device

### Management Stack
- [ ] Autopilot — full integration with ticket-system + LLM decision log
- [ ] GitHub sync test in CI (ticket-push/pull)
- [ ] Monitor daemon — extend health checks to devices stack + HTTP verify

### Testing
- [ ] CLI tests (14 commands)
- [ ] Engine integration tests (implement ticket with each engine)
- [ ] shared/lib unit tests (ticket_system, llm_client)
- [ ] Integration test: wizard → launch → pipeline → deploy → verify

### Docs
- [ ] Video/GIF demo of wizard flow
- [ ] Deployment guide for production multi-server setup
- [ ] Engine comparison benchmark results
