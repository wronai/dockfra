# ═══════════════════════════════════════════════════════════════
# ssh-manager — Project Control Center
# ═══════════════════════════════════════════════════════════════
# Run from repo root:  make -f management/ssh-manager/Makefile <target>
# Or: cd management/ssh-manager && make <target>
# ═══════════════════════════════════════════════════════════════

CONTAINER  ?= dockfra-ssh-manager
ROLE_USER  ?= manager
SSH_PORT   ?= 2202
SSH        := ssh $(ROLE_USER)@localhost -p $(SSH_PORT) -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
EXEC       := docker exec -u $(ROLE_USER) $(CONTAINER) bash -lc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║              👤 MANAGER — Project Control Center             ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  make shell                   — Interactive SSH session      ║"
	@echo "║                                                              ║"
	@echo "║  Ticket Management:                                          ║"
	@echo "║    make status                                               ║"
	@echo "║    make ticket-create TITLE=\"Fix login bug\"                 ║"
	@echo "║    make ticket-list                                          ║"
	@echo "║    make ticket-show   T=T-0001                               ║"
	@echo "║    make ticket-push   T=T-0001                               ║"
	@echo "║    make ticket-pull                                          ║"
	@echo "║                                                              ║"
	@echo "║  Service Configuration:                                      ║"
	@echo "║    make config-developer                                     ║"
	@echo "║    make config-monitor                                       ║"
	@echo "║    make config-show   SVC=developer                         ║"
	@echo "║                                                              ║"
	@echo "║  AI Assistant:                                               ║"
	@echo "║    make ask  Q=\"What is the project status?\"               ║"
	@echo "║    make plan FEATURE=\"user authentication\"                  ║"
	@echo "║                                                              ║"
	@echo "║  Navigation:                                                 ║"
	@echo "║    make ssh-to TARGET=developer|monitor|autopilot            ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""

.PHONY: shell
shell: ## Open interactive SSH session
	@$(SSH)

.PHONY: status
status: ## All services overview
	@$(EXEC) "status"

.PHONY: ticket-create
ticket-create: ## Create ticket: make ticket-create TITLE="Fix login bug"
	@[ -n "$(TITLE)" ] || (echo "Usage: make ticket-create TITLE=\"ticket title\"" && exit 1)
	@$(EXEC) "ticket-create '$(TITLE)'"

.PHONY: ticket-list
ticket-list: ## List all tickets
	@$(EXEC) "ticket-list"

.PHONY: ticket-show
ticket-show: ## Show ticket details: make ticket-show T=T-0001
	@[ -n "$(T)" ] || (echo "Usage: make ticket-show T=T-0001" && exit 1)
	@$(EXEC) "ticket-show $(T)"

.PHONY: ticket-push
ticket-push: ## Push ticket to GitHub: make ticket-push T=T-0001
	@[ -n "$(T)" ] || (echo "Usage: make ticket-push T=T-0001" && exit 1)
	@$(EXEC) "ticket-push $(T)"

.PHONY: ticket-pull
ticket-pull: ## Pull tickets from GitHub
	@$(EXEC) "ticket-pull"

.PHONY: config-developer
config-developer: ## Update developer .env via SSH
	@$(EXEC) "config-developer"

.PHONY: config-monitor
config-monitor: ## Update monitor .env via SSH
	@$(EXEC) "config-monitor"

.PHONY: config-show
config-show: ## Show service LLM config: make config-show SVC=developer
	@[ -n "$(SVC)" ] || (echo "Usage: make config-show SVC=developer" && exit 1)
	@$(EXEC) "config-show $(SVC)"

.PHONY: ask
ask: ## Ask LLM for help: make ask Q="What is the project status?"
	@[ -n "$(Q)" ] || (echo "Usage: make ask Q=\"your question\"" && exit 1)
	@$(EXEC) "ask $(Q)"

.PHONY: plan
plan: ## Generate ticket plan via LLM: make plan FEATURE="user auth"
	@[ -n "$(FEATURE)" ] || (echo "Usage: make plan FEATURE=\"feature description\"" && exit 1)
	@$(EXEC) "plan '$(FEATURE)'"

.PHONY: ssh-to
ssh-to: ## Jump to another node: make ssh-to TARGET=developer|monitor|autopilot
	@[ -n "$(TARGET)" ] || (echo "Usage: make ssh-to TARGET=developer|monitor|autopilot" && exit 1)
	@$(EXEC) "ssh-to $(TARGET)"

.PHONY: logs
logs: ## Tail manager container logs
	@docker logs -f $(CONTAINER)
