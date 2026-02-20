#!/bin/bash
# shared/ssh-base-init.sh — Common SSH container initialization
# Source this from each role's entrypoint.sh after setting SSH_USER.
#
# Required env: SSH_USER (e.g. developer, manager, monitor, autopilot)
# Optional env: SSH_ROLE_LABEL (for log messages, defaults to SSH_USER)

: "${SSH_USER:?SSH_USER must be set}"
ROLE_LABEL="${SSH_ROLE_LABEL:-$SSH_USER}"
UH="/home/$SSH_USER"

echo "[ssh-$ROLE_LABEL] Initializing..."
mkdir -p "$UH/.ssh" /shared/tickets

# ── SSH keys ──────────────────────────────────────────────────
[ -f /keys/deployer.pub ] && cp /keys/deployer.pub "$UH/.ssh/authorized_keys" && chmod 600 "$UH/.ssh/authorized_keys"
[ -f /keys/deployer ]     && cp /keys/deployer "$UH/.ssh/id_rsa" && chmod 600 "$UH/.ssh/id_rsa"

# Copy extra authorized keys from read-only mount (if any)
if [ -d "$UH/.ssh/extra" ]; then
    for k in "$UH/.ssh/extra"/*.pub; do
        [ -f "$k" ] && cat "$k" >> "$UH/.ssh/authorized_keys" 2>/dev/null || true
    done
fi

# Chown .ssh (ignore errors on read-only mounts)
chown -R "$SSH_USER:$SSH_USER" "$UH/.ssh" 2>/dev/null || \
    find "$UH/.ssh" -maxdepth 1 -exec chown "$SSH_USER:$SSH_USER" {} \; 2>/dev/null || true

# ── Service env (LLM config, updatable via SSH) ──────────────
if [ ! -f "$UH/.service-env" ]; then
    env | grep -E '^(OPENROUTER_|LLM_|SERVICE_ROLE|TICKETS_DIR)' > "$UH/.service-env" 2>/dev/null || true
fi
chown "$SSH_USER:$SSH_USER" "$UH/.service-env" 2>/dev/null || true

# ── Base .bashrc (role entrypoint can append to it) ──────────
cat > "$UH/.bashrc" << 'BASHRC'
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null
[ -f ~/.llm-env ] && export $(grep -v '^#' ~/.llm-env | xargs) 2>/dev/null
export PYTHONPATH="/shared/lib:$PYTHONPATH"
export PATH="$HOME/scripts:$PATH"
alias ll='ls -lah'
alias tickets='python3 /shared/lib/ticket_system.py'
alias llm='python3 /shared/lib/llm_client.py'
[ -f /etc/motd ] && cat /etc/motd
BASHRC

# ── .bash_profile: login shells (bash -lc) should also source .bashrc ───
cat > "$UH/.bash_profile" << 'PROFILE'
[ -f ~/.bashrc ] && . ~/.bashrc
PROFILE
chown "$SSH_USER:$SSH_USER" "$UH/.bash_profile" 2>/dev/null || true

# ── Scripts chown + extensionless symlinks ────────────────────
if [ -d "$UH/scripts" ]; then
    chown -R "$SSH_USER:$SSH_USER" "$UH/scripts" 2>/dev/null || true
    # Create symlinks without .sh so commands work as `test-local` not `test-local.sh`
    for f in "$UH/scripts"/*.sh; do
        [ -f "$f" ] || continue
        target="$UH/scripts/$(basename "$f" .sh)"
        [ -e "$target" ] || ln -sf "$f" "$target" 2>/dev/null || true
    done
fi
chown "$SSH_USER:$SSH_USER" "$UH/.bashrc" 2>/dev/null || true
