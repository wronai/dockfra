# ═══════════════════════════════════════════════════════════════
# ssh-autopilot — Autonomous Orchestrator
# ═══════════════════════════════════════════════════════════════
# Run from repo root:  make -f management/ssh-autopilot/Makefile <target>
# Or: cd management/ssh-autopilot && make <target>
# ═══════════════════════════════════════════════════════════════

CONTAINER  ?= dockfra-ssh-autopilot
ROLE_USER  ?= autopilot
SSH_PORT   ?= 2203
SSH        := ssh $(ROLE_USER)@localhost -p $(SSH_PORT) -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
EXEC       := docker exec -u $(ROLE_USER) $(CONTAINER) bash -lc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║              🤖 AUTOPILOT — Autonomous Orchestrator          ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  make shell               — Interactive SSH session          ║"
	@echo "║                                                              ║"
	@echo "║  Commands:                                                   ║"
	@echo "║    make pilot-status                                         ║"
	@echo "║    make pilot-run                                            ║"
	@echo "║    make pilot-plan                                           ║"
	@echo "║    make pilot-log                                            ║"
	@echo "║                                                              ║"
	@echo "║  Ticket Orchestration:                                       ║"
	@echo "║    make ticket-list                                          ║"
	@echo "║    make create-from-plan                                     ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""

.PHONY: shell
shell: ## Open interactive SSH session
	@$(SSH)

.PHONY: pilot-status
pilot-status: ## Show autopilot decisions & state
	@$(EXEC) "pilot-status"

.PHONY: pilot-run
pilot-run: ## Trigger one autopilot cycle manually
	@$(EXEC) "pilot-run"

.PHONY: pilot-plan
pilot-plan: ## Generate project plan via LLM
	@$(EXEC) "pilot-plan"

.PHONY: pilot-log
pilot-log: ## Watch autopilot daemon log (live)
	@$(EXEC) "tail -f /var/log/autopilot.log"

.PHONY: ticket-list
ticket-list: ## List all tickets
	@$(EXEC) "tickets list"

.PHONY: create-from-plan
create-from-plan: ## Create tickets from LLM plan
	@$(EXEC) "create-from-plan"

.PHONY: logs
logs: ## Tail autopilot container logs
	@docker logs -f $(CONTAINER)
