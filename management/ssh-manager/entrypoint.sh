#!/bin/bash
set -e
SSH_USER="manager"
source /ssh-base-init.sh

# ── Manager-specific: SSH client config to other roles ───────
cat > "$UH/.ssh/config" << EOF
Host ssh-developer
    HostName ${SSH_DEVELOPER_HOST:-ssh-developer}
    Port ${SSH_DEVELOPER_PORT:-2222}
    User developer
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
Host ssh-monitor
    HostName ${SSH_MONITOR_HOST:-ssh-monitor}
    Port ${SSH_MONITOR_PORT:-2222}
    User monitor
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
Host ssh-autopilot
    HostName ${SSH_AUTOPILOT_HOST:-ssh-autopilot}
    Port ${SSH_AUTOPILOT_PORT:-2222}
    User autopilot
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
EOF
chown -R manager:manager "$UH/.ssh" 2>/dev/null || true

echo "[ssh-manager] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
