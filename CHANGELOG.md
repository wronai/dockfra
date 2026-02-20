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


