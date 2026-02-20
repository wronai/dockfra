# ═══════════════════════════════════════════════════════════════
# ssh-developer — Ticket-Driven Dev Workspace
# ═══════════════════════════════════════════════════════════════
# Run from repo root:  make -f app/ssh-developer/Makefile <target>
# Or: cd app/ssh-developer && make <target>
#
# All targets use docker exec (no SSH port required).
# ═══════════════════════════════════════════════════════════════

CONTAINER  ?= dockfra-ssh-developer
USER       ?= developer
SSH_PORT   ?= 2200
SSH        := ssh $(USER)@localhost -p $(SSH_PORT) -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
EXEC       := docker exec -it -u $(USER) $(CONTAINER) bash -lc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║         🔧 DEVELOPER — Ticket-Driven Dev Workspace           ║"
	@echo "╠══════════════════════════════════════════════════════════════╣"
	@echo "║  make shell              — Interactive SSH session            ║"
	@echo "║                                                              ║"
	@echo "║  Tickets:                                                    ║"
	@echo "║    make my-tickets                                           ║"
	@echo "║    make ticket-work  T=T-0001                                ║"
	@echo "║    make ticket-done  T=T-0001                                ║"
	@echo "║                                                              ║"
	@echo "║  AI Code Assistant:                                          ║"
	@echo "║    make ask    Q=\"How do I fix X?\"                          ║"
	@echo "║    make review F=src/main.py                                 ║"
	@echo "║    make implement T=T-0001                                   ║"
	@echo "║                                                              ║"
	@echo "║  Dev Tools:                                                  ║"
	@echo "║    make test-local                                           ║"
	@echo "║    make check-services                                       ║"
	@echo "║    make commit-push MSG=\"feat: add feature\"                 ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""

.PHONY: shell
shell: ## Open interactive SSH session
	@$(SSH)

.PHONY: my-tickets
my-tickets: ## List tickets assigned to me
	@$(EXEC) "my-tickets"

.PHONY: ticket-work
ticket-work: ## Start working on ticket: make ticket-work T=T-0001
	@[ -n "$(T)" ] || (echo "Usage: make ticket-work T=T-0001" && exit 1)
	@$(EXEC) "ticket-work $(T)"

.PHONY: ticket-done
ticket-done: ## Mark ticket as done: make ticket-done T=T-0001
	@[ -n "$(T)" ] || (echo "Usage: make ticket-done T=T-0001" && exit 1)
	@$(EXEC) "ticket-done $(T)"

.PHONY: implement
implement: ## AI-assisted implementation: make implement T=T-0001
	@[ -n "$(T)" ] || (echo "Usage: make implement T=T-0001" && exit 1)
	@$(EXEC) "implement $(T)"

.PHONY: ask
ask: ## Ask LLM for help: make ask Q="How do I fix X?"
	@[ -n "$(Q)" ] || (echo "Usage: make ask Q=\"your question\"" && exit 1)
	@$(EXEC) "ask $(Q)"

.PHONY: review
review: ## AI code review: make review F=src/main.py
	@[ -n "$(F)" ] || (echo "Usage: make review F=path/to/file" && exit 1)
	@$(EXEC) "review $(F)"

.PHONY: test-local
test-local: ## Run all local tests
	@$(EXEC) "test-local"

.PHONY: check-services
check-services: ## Check service health
	@$(EXEC) "check-services"

.PHONY: commit-push
commit-push: ## Git commit and push: make commit-push MSG="feat: add feature"
	@[ -n "$(MSG)" ] || (echo "Usage: make commit-push MSG=\"your message\"" && exit 1)
	@$(EXEC) "commit-push '$(MSG)'"

.PHONY: exec-backend
exec-backend: ## Open shell in backend container
	@docker exec -it dockfra-backend bash

.PHONY: exec-frontend
exec-frontend: ## Open shell in frontend container
	@docker exec -it dockfra-frontend sh

.PHONY: exec-db
exec-db: ## Open psql in db container
	@docker exec -it dockfra-db psql -U postgres

.PHONY: logs
logs: ## Tail developer container logs
	@docker logs -f $(CONTAINER)
