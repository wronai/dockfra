#!/bin/bash
set -e
echo "[ssh-developer] Initializing developer workspace..."
DH="/home/developer"
mkdir -p "$DH/.ssh" /shared/tickets

[ -f /keys/deployer.pub ] && cp /keys/deployer.pub "$DH/.ssh/authorized_keys" && chmod 600 "$DH/.ssh/authorized_keys"
[ -f /keys/deployer ] && cp /keys/deployer "$DH/.ssh/id_rsa" && chmod 600 "$DH/.ssh/id_rsa"

# Copy extra authorized keys from read-only mount (if any)
if [ -d "$DH/.ssh/extra" ]; then
    for k in "$DH/.ssh/extra"/*.pub; do
        [ -f "$k" ] && cat "$k" >> "$DH/.ssh/authorized_keys" 2>/dev/null || true
    done
fi

# Chown .ssh but ignore errors on read-only mounts (extra/ is :ro)
chown -R developer:developer "$DH/.ssh" 2>/dev/null || \
    find "$DH/.ssh" -maxdepth 1 -exec chown developer:developer {} \; 2>/dev/null || true

# Git setup
su - developer -c "git config --global user.name developer; git config --global user.email dev@local; git config --global init.defaultBranch main"

# Init repo if needed
[ ! -d /repo/.git ] && su - developer -c "cd /repo && git init && echo '# Dev Repo' > README.md && git add -A && git commit -m 'init' 2>/dev/null || true"
ln -sfn /repo "$DH/workspace/repo" 2>/dev/null || true
chown -R developer:developer "$DH" /repo 2>/dev/null || true

# Service env (LLM config, updatable by manager via SSH)
[ ! -f "$DH/.service-env" ] && env | grep -E '^(OPENROUTER_|LLM_|SERVICE_ROLE|TICKETS_DIR|GITHUB_)' > "$DH/.service-env" 2>/dev/null || true
chown developer:developer "$DH/.service-env"

cat > "$DH/.bashrc" << 'RC'
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null
[ -f ~/.llm-env ] && export $(grep -v '^#' ~/.llm-env | xargs) 2>/dev/null
export PYTHONPATH="/shared/lib:$PYTHONPATH"
export PATH="$HOME/scripts:$PATH"
alias ll='ls -lah'; alias gs='git status'; alias gd='git diff'
alias tickets='python3 /shared/lib/ticket_system.py'
alias llm='python3 /shared/lib/llm_client.py'
alias my-tickets='python3 /shared/lib/ticket_system.py list --assigned=developer'

# docker exec shortcuts (replaces ssh-backend / ssh-frontend bastions)
alias exec-backend='docker exec -it dockfra-backend bash'
alias exec-frontend='docker exec -it dockfra-frontend sh'
alias exec-mobile='docker exec -it dockfra-mobile-backend bash'
alias exec-db='docker exec -it dockfra-db psql -U ${POSTGRES_USER:-postgres}'
alias exec-redis='docker exec -it dockfra-redis redis-cli'
alias dps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias dlogs='docker logs -f'

# volume data shortcuts
alias backend-data='ls -lah /mnt/backend-data/'
alias frontend-data='ls -lah /mnt/frontend-data/'

[ -f /etc/motd ] && cat /etc/motd
RC
chown developer:developer "$DH/.bashrc"

echo "[ssh-developer] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
