# ═══════════════════════════════════════════════════════════════
# ssh-monitor — Deploy & Health Orchestrator
# ═══════════════════════════════════════════════════════════════
# Run from repo root:  make -f management/ssh-monitor/Makefile <target>
# Or: cd management/ssh-monitor && make <target>
# ═══════════════════════════════════════════════════════════════

CONTAINER  ?= dockfra-ssh-monitor
USER       ?= monitor
SSH_PORT   ?= 2201
SSH        := ssh $(USER)@localhost -p $(SSH_PORT) -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
EXEC       := docker exec -it -u $(USER) $(CONTAINER) bash -lc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║              📡 MONITOR — Deploy & Health Orchestrator       ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  make shell           — Interactive SSH session              ║"
	@echo "║                                                              ║"
	@echo "║  Deploy:                                                     ║"
	@echo "║    make status                                               ║"
	@echo "║    make deploy-all                                           ║"
	@echo "║    make deploy-backend                                       ║"
	@echo "║    make deploy-frontend                                      ║"
	@echo "║    make deploy-rpi3                                          ║"
	@echo "║    make verify                                               ║"
	@echo "║                                                              ║"
	@echo "║  AI Analysis:                                                ║"
	@echo "║    make analyze-logs                                         ║"
	@echo "║    make ask Q=\"Why is the backend slow?\"                    ║"
	@echo "║                                                              ║"
	@echo "║  Daemon:                                                     ║"
	@echo "║    make monitor-log   — Watch auto-deploy daemon log         ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""

.PHONY: shell
shell: ## Open interactive SSH session
	@$(SSH)

.PHONY: status
status: ## Full infrastructure status
	@$(EXEC) "status"

.PHONY: deploy-all
deploy-all: ## Deploy to all targets via SSH
	@$(EXEC) "deploy-all"

.PHONY: deploy-backend
deploy-backend: ## Deploy backend only
	@$(EXEC) "deploy-backend"

.PHONY: deploy-frontend
deploy-frontend: ## Deploy frontend only
	@$(EXEC) "deploy-frontend"

.PHONY: deploy-rpi3
deploy-rpi3: ## Deploy to RPi3
	@$(EXEC) "deploy-rpi3"

.PHONY: verify
verify: ## Post-deploy health check
	@$(EXEC) "verify"

.PHONY: analyze-logs
analyze-logs: ## AI analysis of recent logs
	@$(EXEC) "analyze-logs"

.PHONY: ask
ask: ## Ask LLM about infrastructure: make ask Q="Why is the backend slow?"
	@[ -n "$(Q)" ] || (echo "Usage: make ask Q=\"your question\"" && exit 1)
	@$(EXEC) "ask $(Q)"

.PHONY: monitor-log
monitor-log: ## Watch auto-deploy daemon log (live)
	@$(EXEC) "tail -f /var/log/monitor-daemon.log"

.PHONY: logs
logs: ## Tail monitor container logs
	@docker logs -f $(CONTAINER)
