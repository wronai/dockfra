#!/bin/bash
set -e
SSH_USER="autopilot"
source /ssh-base-init.sh

# ── Autopilot-specific: SSH client config ────────────────────
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
EOF
chown -R autopilot:autopilot "$UH/.ssh" 2>/dev/null || true 2>/dev/null || true

# Autopilot aliases
cat >> "$UH/.bashrc" << 'RC'
alias pilot-log='tail -f /var/log/autopilot.log'
RC

# Start autopilot daemon
touch /var/log/autopilot.log && chown autopilot:autopilot /var/log/autopilot.log
echo "[ssh-autopilot] Starting autopilot daemon..."
su - autopilot -c "nohup /home/autopilot/autopilot-daemon.sh >> /var/log/autopilot.log 2>&1 &"

echo "[ssh-autopilot] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
