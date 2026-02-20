#!/bin/bash
set -e
SSH_USER="developer"
source /ssh-base-init.sh

# ── Developer-specific setup ─────────────────────────────────

# Git
su - developer -c "git config --global user.name developer; git config --global user.email dev@local; git config --global init.defaultBranch main"

# Init repo if needed
[ ! -d /repo/.git ] && su - developer -c "cd /repo && git init && echo '# Dev Repo' > README.md && git add -A && git commit -m 'init' 2>/dev/null || true"
ln -sfn /repo "$UH/workspace/repo" 2>/dev/null || true
chown -R developer:developer "$UH" /repo 2>/dev/null || true

# Developer aliases (appended to base .bashrc)
cat >> "$UH/.bashrc" << 'RC'
alias gs='git status'; alias gd='git diff'
alias my-tickets='python3 /shared/lib/ticket_system.py list --assigned=developer'
alias exec-backend='docker exec -it dockfra-backend bash'
alias exec-frontend='docker exec -it dockfra-frontend sh'
alias exec-mobile='docker exec -it dockfra-mobile-backend bash'
alias exec-db='docker exec -it dockfra-db psql -U ${POSTGRES_USER:-postgres}'
alias exec-redis='docker exec -it dockfra-redis redis-cli'
alias dps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias dlogs='docker logs -f'
alias app='cd /workspace/app'
alias edit-backend='cd /workspace/app/backend'
alias edit-frontend='cd /workspace/app/frontend'
alias edit-mobile='cd /workspace/app/mobile-backend'
alias rebuild='docker compose -f /workspace/app/docker-compose.yml up --build -d'
alias rebuild-backend='docker compose -f /workspace/app/docker-compose.yml up --build -d backend'
alias rebuild-frontend='docker compose -f /workspace/app/docker-compose.yml up --build -d frontend'
alias backend-data='ls -lah /mnt/backend-data/'
alias frontend-data='ls -lah /mnt/frontend-data/'
RC

echo "[ssh-developer] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
