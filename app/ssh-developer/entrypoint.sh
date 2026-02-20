#!/bin/bash
set -e
echo "[ssh-developer] Initializing developer workspace..."
DH="/home/developer"
mkdir -p "$DH/.ssh" /shared/tickets

[ -f /keys/deployer.pub ] && cp /keys/deployer.pub "$DH/.ssh/authorized_keys" && chmod 600 "$DH/.ssh/authorized_keys"
[ -f /keys/deployer ] && cp /keys/deployer "$DH/.ssh/id_rsa" && chmod 600 "$DH/.ssh/id_rsa"

chown -R developer:developer "$DH/.ssh"

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
export PYTHONPATH="/shared/lib:$PYTHONPATH"
export PATH="$HOME/scripts:$PATH"
alias ll='ls -lah'; alias gs='git status'; alias gd='git diff'
alias tickets='python3 /shared/lib/ticket_system.py'
alias llm='python3 /shared/lib/llm_client.py'
alias my-tickets='python3 /shared/lib/ticket_system.py list --assigned=developer'
[ -f /etc/motd ] && cat /etc/motd
RC
chown developer:developer "$DH/.bashrc"

echo "[ssh-developer] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
