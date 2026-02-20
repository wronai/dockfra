# ═══════════════════════════════════════════════════════════════
# DOCKFRA — Hybrid Infrastructure Makefile
# ═══════════════════════════════════════════════════════════════
#
# Usage:
#   make init              — Full setup (local)
#   make up                — Start all stacks (app + management + devices)
#   make stop              — Stop all stacks
#   make setup-github      — Copy GitHub SSH keys to developer
#   make setup-llm         — Configure LLM (OpenRouter + getv)
#   make setup-dev-tools   — Install aider, Continue.dev, LiteLLM
#   make ssh-developer     — SSH into developer container
#   make up-devices        — Start devices stack (ssh-rpi3, vnc-rpi3)
#   make deploy-rpi3       — Deploy artifact to RPi3
#
# ═══════════════════════════════════════════════════════════════

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Configuration ──────────────────────────────────────────────
ENVIRONMENT       ?= local
LLM_MODEL         ?= google/gemini-3-flash-preview
DEVELOPER_CONTAINER ?= dockfra-ssh-developer
DEVELOPER_USER    ?= developer
GITHUB_SSH_KEY    ?= $(HOME)/.ssh/id_ed25519
LITELLM_PORT      ?= 4000

# Export for child scripts
export DEVELOPER_CONTAINER DEVELOPER_USER GITHUB_SSH_KEY LLM_MODEL LITELLM_PORT

# ── Paths ──────────────────────────────────────────────────────
ROOT      := $(shell pwd)
APP       := $(ROOT)/app
MGMT      := $(ROOT)/management
DEVICES   := $(ROOT)/devices
SCRIPTS   := $(ROOT)/scripts

# ═══════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════

.PHONY: init
init: ## Full initialization (keys, env, network) and start wizard
	@bash $(ROOT)/init.sh $(ENVIRONMENT)
	@echo "🧙 Starting Dockfra Wizard..."
	@dockfra --root $(ROOT) &
	@sleep 2
	@echo "🌐 Opening Dockfra Wizard in browser..."
	@if command -v xdg-open > /dev/null 2>&1; then \
		xdg-open http://localhost:5050 2>/dev/null || true; \
	elif command -v open > /dev/null 2>&1; then \
		open http://localhost:5050 2>/dev/null || true; \
	else \
		echo "💡 Open http://localhost:5050 in your browser"; \
	fi

.PHONY: init-app
init-app: ## Initialize app stack only
	@bash $(APP)/scripts/init.sh $(ENVIRONMENT)

.PHONY: init-mgmt
init-mgmt: ## Initialize management stack only
	@bash $(MGMT)/scripts/init.sh $(ENVIRONMENT)

.PHONY: init-devices
init-devices: ## Initialize devices stack (ssh-rpi3, vnc-rpi3)
	@bash $(DEVICES)/scripts/init.sh $(ENVIRONMENT)

# ═══════════════════════════════════════════════════════════════
# DOCKER COMPOSE
# ═══════════════════════════════════════════════════════════════

.PHONY: up
up: up-app up-mgmt up-devices ## Start all stacks (app + management + devices)
	@echo "✅ All stacks running"

.PHONY: up-app
up-app: ## Start app stack
	@cd $(APP) && docker compose up -d
	@echo "✅ App stack started"

.PHONY: up-mgmt
up-mgmt: ## Start management stack
	@cd $(MGMT) && docker compose up -d
	@echo "✅ Management stack started"

.PHONY: up-devices
up-devices: ## Start devices stack (ssh-rpi3, vnc-rpi3)
	@cd $(DEVICES) && docker compose up -d
	@echo "✅ Devices stack started"

.PHONY: down-devices
down-devices: ## Stop devices stack
	@cd $(DEVICES) && docker compose down

.PHONY: up-prod
up-prod: ## Start all stacks (production)
	@cd $(APP) && docker compose -f docker-compose-production.yml up -d
	@cd $(MGMT) && docker compose -f docker-compose-production.yml up -d
	@echo "✅ Production stacks started"

.PHONY: down
down: ## Stop all stacks
	@cd $(MGMT) && docker compose down 2>/dev/null || true
	@cd $(APP) && docker compose down 2>/dev/null || true
	@cd $(DEVICES) && docker compose down 2>/dev/null || true
	@echo "✅ All stacks stopped"

.PHONY: stop
stop: ## Stop all stacks and kill services on ports 4000, 5050
	@cd $(MGMT) && docker compose down 2>/dev/null || true
	@cd $(APP) && docker compose down 2>/dev/null || true
	@cd $(DEVICES) && docker compose down 2>/dev/null || true
	@echo "🔍 Killing processes on ports 4000, 5050..."
	@-pkill -f "litellm.*port.*4000" 2>/dev/null || true
	@-pkill -f "python.*5050" 2>/dev/null || true
	@-lsof -ti:4000 | xargs -r kill -9 2>/dev/null || true
	@-lsof -ti:5050 | xargs -r kill -9 2>/dev/null || true
	@echo "✅ All stacks stopped and ports cleared"

.PHONY: down-app
down-app: ## Stop app stack
	@cd $(APP) && docker compose down

.PHONY: down-mgmt
down-mgmt: ## Stop management stack
	@cd $(MGMT) && docker compose down

.PHONY: restart
restart: down up ## Restart both stacks

.PHONY: build
build: ## Build all images
	@cd $(APP) && docker compose build
	@cd $(MGMT) && docker compose build

.PHONY: ps
ps: ## Show running containers
	@echo "── APP ──"
	@cd $(APP) && docker compose ps 2>/dev/null || echo "  (not running)"
	@echo ""
	@echo "── MANAGEMENT ──"
	@cd $(MGMT) && docker compose ps 2>/dev/null || echo "  (not running)"
	@echo ""
	@echo "── DEVICES ──"
	@cd $(DEVICES) && docker compose ps 2>/dev/null || echo "  (not running)"

.PHONY: logs
logs: ## Tail logs (both stacks)
	@docker logs -f $(DEVELOPER_CONTAINER) 2>/dev/null &
	@cd $(MGMT) && docker compose logs -f 2>/dev/null

.PHONY: logs-app
logs-app: ## Tail app stack logs
	@cd $(APP) && docker compose logs -f

.PHONY: logs-mgmt
logs-mgmt: ## Tail management stack logs
	@cd $(MGMT) && docker compose logs -f

# ═══════════════════════════════════════════════════════════════
# GITHUB + LLM SETUP
# ═══════════════════════════════════════════════════════════════

.PHONY: setup-github
setup-github: ## Copy host GitHub SSH keys + git config into ssh-developer
	@bash $(SCRIPTS)/setup-github-keys.sh

.PHONY: setup-llm
setup-llm: ## Configure LLM (OpenRouter API key via getv + LiteLLM)
	@bash $(SCRIPTS)/setup-llm.sh

.PHONY: setup-dev-tools
setup-dev-tools: ## Install dev tools: aider, Continue.dev, Claude proxy
	@bash $(SCRIPTS)/setup-dev-tools.sh

.PHONY: setup-all
setup-all: setup-github setup-llm setup-dev-tools ## Full developer setup (GitHub + LLM + tools)
	@echo ""
	@echo "╔══════════════════════════════════════════╗"
	@echo "║  Developer fully configured!             ║"
	@echo "╚══════════════════════════════════════════╝"
	@echo "  make ssh-developer    — SSH into workspace"
	@echo "  aider-start           — AI pair programming"
	@echo "  litellm-start         — Start LiteLLM proxy"

.PHONY: inject-env
inject-env: ## Inject getv profile: make inject-env CATEGORY=llm PROFILE=openrouter
	@bash $(SCRIPTS)/inject-getv-env.sh $(DEVELOPER_CONTAINER) $(CATEGORY) $(PROFILE)

# ═══════════════════════════════════════════════════════════════
# SSH ACCESS
# ═══════════════════════════════════════════════════════════════

.PHONY: ssh-developer
ssh-developer: ## SSH into developer container
	@ssh developer@localhost -p 2200 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

.PHONY: ssh-manager
ssh-manager: ## SSH into manager container
	@ssh manager@localhost -p 2202 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

.PHONY: ssh-autopilot
ssh-autopilot: ## SSH into autopilot container
	@ssh autopilot@localhost -p 2203 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

.PHONY: ssh-monitor
ssh-monitor: ## SSH into monitor container
	@ssh monitor@localhost -p 2201 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

.PHONY: ssh-rpi3
ssh-rpi3: ## SSH into ssh-rpi3 container (devices stack)
	@ssh deployer@localhost -p 2224 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null

.PHONY: vnc-rpi3
vnc-rpi3: ## Open VNC web UI for RPi3 in browser
	@echo "Open: http://localhost:6080"
	@xdg-open http://localhost:6080 2>/dev/null || open http://localhost:6080 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════
# DEVICES — RPi3 deploy
# ═══════════════════════════════════════════════════════════════

.PHONY: deploy-rpi3
deploy-rpi3: ## Deploy artifact to RPi3: make deploy-rpi3 ARTIFACT=/artifacts/app.tar.gz
	@bash $(DEVICES)/scripts/deploy.sh $(ARTIFACT)

.PHONY: setup-devices-keys
setup-devices-keys: ## Copy SSH keys into devices stack
	@bash $(DEVICES)/scripts/setup-keys.sh

# ═══════════════════════════════════════════════════════════════
# LLM TOOLS (remote execution inside developer)
# ═══════════════════════════════════════════════════════════════

.PHONY: aider
aider: ## Start aider inside ssh-developer
	@docker exec -it -u $(DEVELOPER_USER) $(DEVELOPER_CONTAINER) bash -lc 'cd /repo && source ~/.llm-env && aider --model openrouter/$(LLM_MODEL)'

.PHONY: litellm
litellm: ## Start LiteLLM proxy inside ssh-developer (port 4000)
	@docker exec -d -u $(DEVELOPER_USER) $(DEVELOPER_CONTAINER) bash -lc 'source ~/.llm-env && litellm --config ~/.litellm/config.yaml --port $(LITELLM_PORT)'
	@echo "✅ LiteLLM proxy started on port $(LITELLM_PORT)"
	@echo "   Health: docker exec $(DEVELOPER_CONTAINER) curl -s http://localhost:$(LITELLM_PORT)/health"

.PHONY: llm-ask
llm-ask: ## Ask LLM a question: make llm-ask Q="your question"
	@docker exec -u $(DEVELOPER_USER) $(DEVELOPER_CONTAINER) bash -lc 'source ~/.llm-env && python3 /shared/lib/llm_client.py ask "$(Q)"'

# ═══════════════════════════════════════════════════════════════
# GETV INTEGRATION
# ═══════════════════════════════════════════════════════════════

.PHONY: getv-list
getv-list: ## List getv profiles
	@getv list

.PHONY: getv-show-llm
getv-show-llm: ## Show LLM profile
	@getv list llm openrouter

.PHONY: getv-set-key
getv-set-key: ## Set OpenRouter API key: make getv-set-key KEY=sk-or-v1-...
	@getv set llm openrouter OPENROUTER_API_KEY=$(KEY)
	@echo "✅ Key saved. Run: make setup-llm"

# ═══════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════

.PHONY: test
test: ## Run E2E test suite
	@bash $(ROOT)/tests/run-tests.sh

.PHONY: test-github
test-github: ## Test GitHub SSH access from developer
	@docker exec -u $(DEVELOPER_USER) $(DEVELOPER_CONTAINER) ssh -T git@github.com -o ConnectTimeout=10 2>&1 || true

.PHONY: test-llm
test-llm: ## Test LLM connectivity from developer
	@docker exec -u $(DEVELOPER_USER) $(DEVELOPER_CONTAINER) bash -lc 'source ~/.llm-env && python3 -c "import os,urllib.request,json; key=os.environ.get(\"OPENROUTER_API_KEY\",\"\"); model=os.environ.get(\"LLM_MODEL\",\"google/gemini-3-flash-preview\"); req=urllib.request.Request(\"https://openrouter.ai/api/v1/models\",headers={\"Authorization\":f\"Bearer {key}\"}); data=json.loads(urllib.request.urlopen(req,timeout=10).read()); print(f\"OK — {len(data.get(chr(100)+chr(97)+chr(116)+chr(97),[]))} models, using: {model}\")"'

.PHONY: test-ssh
test-ssh: ## Test SSH connectivity to all roles
	@echo "Testing SSH ports..."
	@for p in 2200 2201 2202 2203; do \
		timeout 3 bash -c "echo >/dev/tcp/localhost/$$p" 2>/dev/null && echo "  ✅ :$$p open" || echo "  ❌ :$$p closed"; \
	done

# ═══════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════

.PHONY: clean
clean: down ## Stop stacks and remove volumes
	@cd $(APP) && docker compose down -v 2>/dev/null || true
	@cd $(MGMT) && docker compose down -v 2>/dev/null || true
	@echo "✅ Cleaned up"

.PHONY: clean-keys
clean-keys: ## Remove generated SSH keys
	@rm -rf $(MGMT)/keys/manager/id_ed25519* $(MGMT)/keys/autopilot/id_ed25519* $(MGMT)/keys/monitor/id_ed25519*
	@rm -f $(MGMT)/keys/deployer $(MGMT)/keys/deployer.pub $(MGMT)/keys/config
	@rm -f $(APP)/ssh-developer/keys/id_ed25519* $(APP)/ssh-developer/keys/deployer*
	@echo "✅ Keys removed (regenerate with: make init)"

# ═══════════════════════════════════════════════════════════════
# WIZARD
# ═══════════════════════════════════════════════════════════════

.PHONY: wizard
wizard: ## Start interactive setup wizard at http://localhost:5050
	@dockfra --root $(ROOT)

.PHONY: wizard-bg
wizard-bg: ## Start wizard in background
	@dockfra --root $(ROOT) &
	@sleep 1 && xdg-open http://localhost:5050 2>/dev/null || open http://localhost:5050 2>/dev/null || echo "Open: http://localhost:5050"

.PHONY: dashboard
dashboard: ## Open management dashboard in browser (requires wizard running)
	@xdg-open http://localhost:5050/dashboard 2>/dev/null || open http://localhost:5050/dashboard 2>/dev/null || echo "Open: http://localhost:5050/dashboard"

.PHONY: desktop
desktop: ## Open management desktop (noVNC) in browser
	@echo "Open: http://localhost:6081"
	@xdg-open http://localhost:6081 2>/dev/null || open http://localhost:6081 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════
# HELP
# ═══════════════════════════════════════════════════════════════

.PHONY: help
help: ## Show this help
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║  DOCKFRA — Hybrid Infrastructure Makefile                   ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "  Config:"
	@echo "    LLM_MODEL=$(LLM_MODEL)"
	@echo "    ENVIRONMENT=$(ENVIRONMENT)"
	@echo "    GITHUB_SSH_KEY=$(GITHUB_SSH_KEY)"
