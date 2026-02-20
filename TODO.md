# Dockfra TODO

_Last updated: 2026-02-20 — 8 modules, 3807 lines, 135 functions_

---

## ✅ Completed

### Core & Architecture
- [x] Python package refactor: `dockfra/` with core.py, app.py, steps.py, fixes.py, discover.py, cli.py
- [x] Central `PROJECT` config with `cname()`, `short_name()` — configurable via `DOCKFRA_PREFIX`
- [x] Auto-discover stacks from subdirectories with `docker-compose.yml` (`STACKS` dict)
- [x] Auto-discover env vars from compose files — parses `${VAR:-default}` patterns (55+ vars)
- [x] `_build_env_schema()` — merges core + discovered + dockfra.yaml overrides (62 entries)
- [x] Auto-generate `_ENV_TO_STATE` from `ENV_SCHEMA` (eliminated manual 22-line mapping)
- [x] `dockfra.yaml` optional project config — override labels, types, groups, descriptions
- [x] `_FIELD_META` — built-in descriptions for 40+ commonly used Docker variables
- [x] Dynamic `_WIZARD_SYSTEM_PROMPT` — built from discovered stacks
- [x] Dynamic `COMMON_PORTS` — built from ENV_SCHEMA port defaults
- [x] Shared SSH base image (`shared/Dockerfile.ssh-base`) + per-role thin Dockerfiles
- [x] Shared entrypoint init (`shared/ssh-base-init.sh`)
- [x] Backward-compatible aliases: `MGMT`, `APP`, `DEVS` from `STACKS`

### Wizard
- [x] Web setup wizard — Flask + SocketIO chat UI (652 + 1012 lines)
- [x] Dynamic widgets: buttons, text_input (chips + eye toggle + desc + autodetect), select, code_block, progress, status_row, action_grid
- [x] Inline missing-field forms with preflight checks
- [x] Smart suggestions: git config/repo/branch, SSH keys, Docker networks, ARP scan, free ports, secrets
- [x] ⚡ Auto-detect buttons for GIT_REPO_URL, GIT_BRANCH, APP_VERSION, APP_NAME
- [x] ℹ️ Field descriptions with help tooltips
- [x] DEVICE_IP priority chain: `devices/.env` → docker inspect → ARP REACHABLE → ARP STALE
- [x] Eye toggle on all password/secret fields
- [x] Settings sections with ✅/🔴N completeness icons
- [x] 10 European languages (pl, en, de, fr, es, it, pt, cs, ro, nl)
- [x] Docker Compose error analysis + interactive fix buttons
- [x] Dashboard at `/dashboard` — real-time container status + decision log
- [x] REST API: `/api/env`, `/api/containers`, `/api/processes`, `/api/action`, `/api/detect/<key>`
- [x] Git clone integration — clone app repo on first launch via `GIT_REPO_URL`
- [x] Virtual developer role — shown when `app/` not cloned but `GIT_REPO_URL` set
- [x] `[[label|action]]` inline action links in chat messages
- [x] Shared `_dispatch()` for consistent SocketIO + REST API handling

### Infrastructure
- [x] Ticket-driven workflow with GitHub Issues sync
- [x] Autopilot daemon with LLM decision loop
- [x] SSH role isolation (4 roles: developer, manager, monitor, autopilot)
- [x] Auto-repair: container restart, network overlap, ACME, volume perms, Docker socket
- [x] Unified scripts directory per role
- [x] shared/lib/ — llm_client.py, ticket_system.py, logger.py

### Documentation
- [x] docs/ARCHITECTURE.md — system design, modules, data flow
- [x] docs/CONFIGURATION.md — dockfra.yaml, ENV_SCHEMA, auto-discovery
- [x] docs/GETTING-STARTED.md — quickstart for any Docker project
- [x] docs/SSH-ROLES.md — role system, commands, isolation
- [x] docs/WIZARD-API.md — REST + WebSocket API reference
- [x] comparisons/ — vs Kamal, Coolify, Portainer, CrewAI/AutoGen, OpenDevin/Aider

---

## In Progress

- [ ] Post-launch plugin system — config-driven UI from `dockfra.yaml` (see `docs/PLAN-post-launch-plugins.md`)

---

## Pending

### Core
- [ ] `dockfra.yaml` `post_launch` hooks — config-driven post-launch buttons and actions
- [ ] `dockfra.yaml` `fixes` section — project-specific fix plugins
- [ ] Condition evaluators: `stack_running()`, `container_running()`, `ssh_roles_exist()`
- [ ] i18n for all Python-side messages (currently Polish; `lang:` from dockfra.yaml)

### Wizard
- [ ] Wizard authentication — token or password protection
- [ ] Wizard Docker container — Dockerfile + add to management/docker-compose.yml
- [ ] Persistent `_state` across restarts (save to `dockfra/.env` on shutdown)
- [ ] WebSocket streaming optimization (batch log lines)

### App Stack
- [ ] Generic app scaffolding — templates for common frameworks (Django, FastAPI, Next.js)
- [ ] Database migrations — Alembic/Flyway integration
- [ ] Health endpoint auto-detection from compose labels

### Devices Stack
- [ ] Auto-ping sweep when ARP cache is empty
- [ ] SSH key auto-install to target device
- [ ] Validate device reachability before launching devices stack

### Management Stack
- [ ] Autopilot — full integration with ticket-system + LLM decision log
- [ ] GitHub sync test in CI (ticket-push/pull)
- [ ] Monitor daemon — extend health checks to devices stack

### Testing
- [ ] Wizard API endpoint tests (all `/api/*` routes)
- [ ] Integration test: wizard → launch → container health check
- [ ] shared/lib unit tests (ticket_system: 14 functions, llm_client: 4 functions)
- [ ] CLI tests (21 commands)

### Docs
- [ ] Video/GIF demo of wizard flow
- [ ] API reference for app/backend REST endpoints
- [ ] Deployment guide for production multi-server setup
