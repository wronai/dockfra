# Dockfra TODO

_Last updated: 2026-02-20 based on `project.functions.toon` (14 modules, 158 functions)_

---

## ✅ Completed

- [x] Web setup wizard — Flask + SocketIO chat UI (`wizard/app.py`, 64 functions)
- [x] Dynamic widgets: buttons, text_input (chips + eye toggle), select, code_block, progress, status_row
- [x] ENV_SCHEMA: centralized env var config with `load_env` / `save_env` / `wizard/.env`
- [x] Preflight checks with inline form fields (not just text warnings)
- [x] Smart suggestions: git config, SSH keys, Docker networks, ARP scan, free ports, secrets
- [x] DEVICE_IP priority chain: `devices/.env` → docker inspect → ARP REACHABLE → ARP STALE
- [x] ARP device discovery with state (REACHABLE/STALE/DELAY) — icon-coded chips
- [x] Eye toggle on all password/secret fields
- [x] Status icons merged into settings section buttons — no separate list
- [x] Multilanguage support — 10 EU languages (pl, en, de, fr, es, it, pt, cs, ro, nl)
- [x] Language selector in header, persisted to localStorage
- [x] Static file split: wizard.css + wizard.js extracted from index.html
- [x] Panel resize handles (chat / processes / logs)
- [x] Processes panel with container stop/restart/port-change actions
- [x] Docker Compose error analysis + interactive solution buttons
- [x] Desktop container (noVNC + Chromium) in management stack
- [x] Dashboard at /dashboard with real-time container status + structured JSONL logs
- [x] Structured JSON logger (management/shared/lib/logger.py)
- [x] Devices stack: ssh-rpi3, vnc-rpi3 services
- [x] Duplicate widget fix: targeted SocketIO emits via thread-local SID
- [x] shared/lib/ — llm_client.py, ticket_system.py

---

## In Progress

- [ ] Interactive end-to-end test — full flow: welcome → fill missing vars → launch stacks → deploy to device

---

## Pending

### Wizard
- [ ] LLM integration in wizard — chat messages routed to llm_client.chat() for AI assistance
- [ ] Wizard authentication — simple token or password protection for the web UI
- [ ] WebSocket streaming for docker compose output (currently buffered per-line)
- [ ] Persistent state across restarts — save _state to wizard/.env on shutdown
- [ ] Wizard Docker container — wizard/Dockerfile + add to management/docker-compose.yml

### App Stack (app/)
- [ ] app/backend/app.py — extend REST API (currently 8 endpoints: health, db, redis, info, echo, init_db)
- [ ] app/mobile-backend/app.py — full sync/register logic (currently 4 endpoints)
- [ ] app/desktop-app/src/main.py — desktop UI beyond check_backend + main
- [ ] Database migrations — replace init_db() with Alembic or Flyway

### Devices Stack (devices/)
- [ ] Auto-ping sweep on subnet when ARP cache is empty
- [ ] SSH key auto-install to target device from wizard
- [ ] Validate RPI3_HOST reachability before launching devices stack

### Management Stack
- [ ] Autopilot daemon full integration with ticket-system + LLM decision log
- [ ] ticket-push / ticket-pull GitHub sync test in CI
- [ ] Monitor daemon — extend health checks to devices stack containers

### Testing
- [ ] Wizard API endpoint tests (/api/env, /api/processes, /api/history)
- [ ] Integration test: wizard → launch → container running
- [ ] shared/lib/ticket_system.py unit tests (14 functions)
- [ ] shared/lib/llm_client.py mock tests

### Docs
- [ ] Architecture diagram update (add wizard + devices stack)
- [ ] API reference for app/backend REST endpoints
- [ ] Video/GIF demo of wizard flow
