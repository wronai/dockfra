#!/bin/bash
set -e
echo "[ssh-manager] Initializing manager workspace..."

MH="/home/manager"
mkdir -p "$MH/.ssh" /shared/tickets

# SSH keys
[ -f /keys/deployer.pub ] && cp /keys/deployer.pub "$MH/.ssh/authorized_keys" && chmod 600 "$MH/.ssh/authorized_keys"
[ -f /keys/deployer ] && cp /keys/deployer "$MH/.ssh/id_rsa" && chmod 600 "$MH/.ssh/id_rsa"

# SSH client config for reaching other services
cat > "$MH/.ssh/config" << EOF
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

chown -R manager:manager "$MH/.ssh" "$MH/scripts"

# Bashrc
cat > "$MH/.bashrc" << 'RC'
export PYTHONPATH="/shared/lib:$PYTHONPATH"
export PATH="$HOME/scripts:$PATH"
[ -f /etc/motd ] && cat /etc/motd
alias ll='ls -lah'
alias tickets='python3 /shared/lib/ticket_system.py'
alias llm='python3 /shared/lib/llm_client.py'
RC

chown manager:manager "$MH/.bashrc"
echo "[ssh-manager] Ready. Starting SSH on :2222..."
exec /usr/sbin/sshd -D -e
