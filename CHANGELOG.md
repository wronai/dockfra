## [1.0.31] - 2026-02-21

### Summary

refactor(docs): configuration management system

### Other

- update dockfra/app.py
- update dockfra/core.py
- update shared/lib/ticket_system.py


## [1.0.30] - 2026-02-21

### Summary

docs(docs): configuration management system

### Other

- update dockfra/app.py
- update dockfra/core.py


## [1.0.29] - 2026-02-21

### Summary

docs(docs): deep code analysis engine with 2 supporting modules

### Other

- update dockfra/app.py
- update dockfra/static/wizard.css
- update dockfra/static/wizard.js
- update dockfra/templates/index.html


## [1.0.28] - 2026-02-20

### Summary

refactor(docs): configuration management system

### Docs

- docs: update README
- docs: update TODO.md


## [1.0.28] - 2026-02-20

### Summary

docs(docs): comprehensive documentation, comparisons, generification

### Features

- **Auto-discover stacks** — `_discover_stacks()` scans ROOT for subdirs with `docker-compose.yml`
- **Auto-discover env vars** — `_parse_compose_env_vars()` extracts `${VAR:-default}` from compose files (55+ vars)
- **`dockfra.yaml`** — optional project config for label/type/group overrides
- **`_build_env_schema()`** — merges core + discovered + yaml overrides (62 entries)
- **Auto `_ENV_TO_STATE`** — generated from ENV_SCHEMA (eliminated 22-line manual mapping)
- **Dynamic `_WIZARD_SYSTEM_PROMPT`** — built from discovered stacks
- **Dynamic `COMMON_PORTS`** — built from ENV_SCHEMA port defaults
- **`_FIELD_META`** — descriptions for 40+ commonly used Docker variables

### Docs

- docs: create docs/ARCHITECTURE.md — system design, modules, data flow
- docs: create docs/CONFIGURATION.md — dockfra.yaml, ENV_SCHEMA, auto-discovery
- docs: create docs/GETTING-STARTED.md — quickstart for any Docker project
- docs: create docs/SSH-ROLES.md — role system, commands, isolation
- docs: create docs/WIZARD-API.md — REST + WebSocket API reference
- docs: create comparisons/README.md — overview matrix (9 systems)
- docs: create comparisons/vs-kamal.md — vs Basecamp Kamal
- docs: create comparisons/vs-coolify.md — vs Coolify self-hosted PaaS
- docs: create comparisons/vs-portainer.md — vs Portainer Docker GUI
- docs: create comparisons/vs-multi-agent-frameworks.md — vs CrewAI, AutoGen, LangGraph
- docs: create comparisons/vs-ai-dev-agents.md — vs OpenDevin, Devika, SWE-Agent, Aider
- docs: rewrite README.md — current architecture, features, links to docs/ and comparisons/
- docs: rewrite TODO.md — current state with 56 completed items


## [1.0.27] - 2026-02-20

### Summary

docs(docs): deep code analysis engine with 6 supporting modules

### Docs

- docs: update README
- docs: update vs-kamal.md
- docs: update WIZARD-API.md


## [1.0.26] - 2026-02-20

### Summary

docs(docs): deep code analysis engine with 3 supporting modules

### Docs

- docs: update GETTING-STARTED.md
- docs: update SSH-ROLES.md

### Other

- update dockfra/app.py
- update dockfra/steps.py


## [1.0.25] - 2026-02-20

### Summary

docs(docs): configuration management system

### Docs

- docs: update ARCHITECTURE.md
- docs: update CONFIGURATION.md


## [1.0.24] - 2026-02-20

### Summary

docs(docs): docs module improvements

### Other

- update dockfra/steps.py


## [1.0.23] - 2026-02-20

### Summary

docs(docs): configuration management system

### Other

- update dockfra/app.py
- update dockfra/core.py
- update dockfra/static/wizard.css
- update dockfra/static/wizard.js
- update dockfra/steps.py


## [1.0.22] - 2026-02-20

### Summary

fix(docs): configuration management system

### Docs

- docs: update PLAN-post-launch-plugins.md

### Other

- update dockfra/core.py
- update dockfra/discover.py
- update dockfra/fixes.py
- update dockfra/static/wizard.css
- update dockfra/static/wizard.js
- update dockfra/steps.py
- scripts: update ssh-base-init.sh


## [1.0.21] - 2026-02-20

### Summary

docs(docs): configuration management system

### Other

- update dockfra/app.py
- update dockfra/core.py
- update dockfra/discover.py
- update dockfra/fixes.py
- update dockfra/static/wizard.css
- update dockfra/static/wizard.js
- update dockfra/steps.py


## [1.0.20] - 2026-02-20

### Summary

refactor(goal): CLI interface with 2 supporting modules

### Other

- update management/shared/lib/__init__.py
- update management/shared/lib/llm_client.py
- update management/shared/lib/ticket_system.py
- update shared/lib/logger.py


## [1.0.19] - 2026-02-20

### Summary

feat(docs): configuration management system

### Other

- build: update Makefile
- docker: update Dockerfile
- scripts: update entrypoint.sh
- scripts: update ask.sh
- update dockfra/core.py
- update dockfra/discover.py
- update dockfra/static/wizard.css
- update dockfra/static/wizard.js
- update dockfra/steps.py
- docker: update Dockerfile
- ... and 34 more


## [1.0.18] - 2026-02-20

### Summary

fix(docs): deep code analysis engine with 3 supporting modules

### Other

- config: update docker-compose-production.yml
- docker: update docker-compose.yml
- scripts: update entrypoint.sh
- update dockfra/app.py


## [1.0.17] - 2026-02-20

### Summary

refactor(docs): configuration management system

### Other

- update dockfra/app.py
- update dockfra/core.py
- update dockfra/discover.py
- update dockfra/fixes.py
- update dockfra/steps.py


## [1.0.16] - 2026-02-20

### Summary

docs(docs): configuration management system

### Other

- update dockfra/app.py


## [1.0.15] - 2026-02-20

### Summary

feat(build): configuration management system

### Other

- build: update Makefile
- docker: update docker-compose.yml
- scripts: update generate-developer-keys.sh
- build: update Makefile
- scripts: update entrypoint.sh
- update dockfra/app.py
- update dockfra/static/wizard.js
- scripts: update sync-keys-to-developer.sh
- build: update Makefile
- build: update Makefile
- ... and 1 more


## [1.0.14] - 2026-02-20

### Summary

feat(docs): configuration management system

### Config

- config: update goal.yaml

### Other

- docker: update docker-compose.yml
- update dockfra/app.py
- docker: update docker-compose.yml


## [1.0.13] - 2026-02-20

### Summary

feat(wizard): configuration management system

### Other

- update project.functions.toon
- update project.toon-schema.json
- update wizard/app.py


## [1.0.13] - 2026-02-20

### Summary

feat(wizard): full interactive setup wizard — multilanguage, smart suggestions, ARP discovery, static file split

### Wizard — Backend (`wizard/app.py`, 64 functions)

- feat: `step_welcome()` now renders inline form fields for missing env vars instead of a text warning
- feat: `_detect_suggestions()` — auto-detects git config, SSH keys, OpenRouter env var, free ports, app version from git tag, app name from project directory
- feat: `_arp_devices()` — ARP cache scan via `ip neigh` with state detection (REACHABLE/STALE/DELAY/FAILED/UNKNOWN), sorted REACHABLE-first
- feat: `_devices_env_ip()` — reads `RPI3_HOST` from `devices/.env.local` / `devices/.env`
- feat: `_docker_container_env()` — extracts env vars from running Docker containers (`dockfra-ssh-rpi3`)
- feat: `_local_interfaces()` — detects host IPs to exclude from device suggestions
- feat: DEVICE_IP priority chain: `devices/.env` → `docker inspect ssh-rpi3` → ARP REACHABLE → ARP STALE
- feat: `text_input()` extended with `hint` and `chips` parameters
- feat: `_emit_missing_fields()` passes chips + hints to every field widget
- feat: `step_settings()` — removed separate `status_row`, merged ✅/🔴N status icons into section buttons
- feat: random secret generation (3 chips per secret field, clickable to insert)
- feat: SSH key chips (all `~/.ssh/id_*` keys as clickable chips)

### Wizard — Frontend

- feat(`wizard/static/wizard.js`): extracted from inline `<script>` — 20 JS functions
- feat(`wizard/static/wizard.css`): extracted from inline `<style>` — all styling
- refactor(`wizard/templates/index.html`): reduced to pure HTML shell (54 lines) with `<link>` + `<script src>`
- feat: `renderInput()` — eye 👁 toggle button for password fields (show/hide)
- feat: `renderInput()` — clickable suggestion chips (`.chip`) below each input
- feat: i18n support — `TRANSLATIONS` object with 10 European languages (pl, en, de, fr, es, it, pt, cs, ro, nl)
- feat: language selector dropdown in header, persisted to `localStorage`
- feat: `applyLang()` updates all static UI strings on language change
- feat: connection status uses translated strings

### CSS (`wizard/static/wizard.css`)

- feat: `.field-input-wrap` + `.eye-btn` — password reveal toggle styling
- feat: `.field-chips` + `.chip` + `.chip.active` — suggestion chip row styling
- feat: `.field-hint` — italic hint text below inputs

## [1.0.12] - 2026-02-20

### Summary

feat(wizard): configuration management system

### Other

- update wizard/app.py
- update wizard/static/wizard.css
- update wizard/static/wizard.js


## [1.0.11] - 2026-02-20

### Summary

feat(wizard): deep code analysis engine with 3 supporting modules

### Other

- update wizard/app.py
- update wizard/static/wizard.css
- update wizard/templates/index.html


## [1.0.10] - 2026-02-20

### Summary

feat(docs): configuration management system

### Docs

- docs: update TODO.md

### Other

- update wizard/app.py
- update wizard/templates/index.html


## [1.0.9] - 2026-02-20

### Summary

feat(docs): docs module improvements

### Other

- docker: update docker-compose.yml
- update wizard/templates/index.html


## [1.0.8] - 2026-02-20

### Summary

feat(wizard): deep code analysis engine with 2 supporting modules

### Other

- update wizard/app.py
- update wizard/requirements.txt
- update wizard/templates/index.html


## [1.0.7] - 2026-02-20

### Summary

feat(build): CLI interface with 3 supporting modules

### Config

- config: update goal.yaml

### Other

- build: update Makefile
- update wizard/app.py
- update wizard/requirements.txt
- update wizard/templates/index.html


## [1.0.6] - 2026-02-20

### Summary

feat(docs): configuration management system

### Docs

- docs: update README

### Test

- scripts: update run-tests.sh

### Other

- update .gitignore
- docker: update docker-compose.yml
- config: update docker-compose-production.yml
- docker: update docker-compose.yml
- update wizard/app.py
- update wizard/templates/index.html


## [1.0.5] - 2026-02-20

### Summary

refactor(docs): commit message generator

### Docs

- docs: update README
- docs: update hybrid.md

### Test

- scripts: update run-tests.sh

### Config

- config: update goal.yaml

### Other

- build: update Makefile
- docker: update Dockerfile
- update app/ssh-developer/motd
- scripts: update ask.sh
- scripts: update check-services.sh
- scripts: update commit-push.sh
- scripts: update implement.sh
- scripts: update my-tickets.sh
- scripts: update review.sh
- scripts: update test-local.sh
- ... and 15 more


## [1.0.4] - 2026-02-20

### Summary

feat(build): configuration management system

### Test

- scripts: update run-tests.sh

### Other

- build: update Makefile
- config: update docker-compose-production.yml
- docker: update docker-compose.yml
- config: update docker-compose-production.yml
- docker: update docker-compose.yml
- scripts: update deploy.sh
- scripts: update init.sh
- scripts: update setup-keys.sh
- docker: update Dockerfile
- scripts: update entrypoint-rpi3.sh
- ... and 2 more


## [1.0.3] - 2026-02-20

### Summary

refactor(build): configuration management system

### Docs

- docs: update README

### Test

- scripts: update run-tests.sh

### Refactor

- refactor: move app/shared/lib to shared/lib for better architecture
- refactor: update all docker-compose.yml volume paths
- refactor: update test paths and gitignore rules

### Other

- update .env.local
- update .env.production
- update .gitignore
- build: update Makefile
- config: update docker-compose-production.yml
- docker: update docker-compose.yml
- scripts: update entrypoint.sh
- update app/ssh-developer/keys/.gitkeep
- update management/keys/.gitkeep
- update management/keys/autopilot/.gitkeep
- ... and 8 more


## [1.0.2] - 2026-02-20

### Summary

feat(docs): commit message generator

### App

- update app/backend/app.py
- update app/backend/tests/test_api.py
- update app/desktop-app/server.py
- update app/desktop-app/src/main.py
- update app/mobile-backend/app.py
- update app/shared/lib/__init__.py
- update app/shared/lib/llm_client.py
- update app/shared/lib/ticket_system.py

### Docs

- docs: update README
- docs: update hybrid.md

### Other

- update .gitignore
- docker: update Dockerfile
- update app/backend/requirements.txt
- docker: update Dockerfile
- scripts: update build.sh
- config: update docker-compose-production.yml
- docker: update docker-compose.yml
- docker: update Dockerfile
- update app/frontend/nginx.conf
- update app/frontend/public/index.html
- ... and 68 more


## [1.0.1] - 2026-02-20

### Summary

feat(docs): commit message generator

### Docs

- docs: update README

### Config

- config: update goal.yaml

### Other

- update .env.local
- update .env.production
- update .gitignore
- docker: update Dockerfile
- update backend/app.py
- update backend/requirements.txt
- update backend/tests/test_api.py
- docker: update Dockerfile
- scripts: update build.sh
- update desktop-app/server.py
- ... and 61 more


