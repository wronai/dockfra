#!/bin/bash
set -e
echo "[ssh-autopilot] Initializing autonomous orchestrator..."
AH="/home/autopilot"
mkdir -p "$AH/.ssh" /shared/tickets

[ -f /keys/deployer.pub ] && cp /keys/deployer.pub "$AH/.ssh/authorized_keys" && chmod 600 "$AH/.ssh/authorized_keys"
[ -f /keys/deployer ] && cp /keys/deployer "$AH/.ssh/id_rsa" && chmod 600 "$AH/.ssh/id_rsa"

cat > "$AH/.ssh/config" << EOF
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
chown -R autopilot:autopilot "$AH/.ssh"

[ ! -f "$AH/.service-env" ] && env | grep -E '^(OPENROUTER_|LLM_|SERVICE_ROLE|TICKETS_DIR|AUTOPILOT_)' > "$AH/.service-env" 2>/dev/null || true
chown autopilot:autopilot "$AH/.service-env"

cat > "$AH/.bashrc" << 'RC'
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null
export PYTHONPATH="/shared/lib:$PYTHONPATH"
export PATH="$HOME/scripts:$PATH"
alias ll='ls -lah'; alias tickets='python3 /shared/lib/ticket_system.py'
alias llm='python3 /shared/lib/llm_client.py'; alias pilot-log='tail -f /var/log/autopilot.log'
[ -f /etc/motd ] && cat /etc/motd
RC
chown autopilot:autopilot "$AH/.bashrc"

touch /var/log/autopilot.log && chown autopilot:autopilot /var/log/autopilot.log
echo "[ssh-autopilot] Starting autopilot daemon..."
su - autopilot -c "nohup /home/autopilot/autopilot-daemon.sh >> /var/log/autopilot.log 2>&1 &"

echo "[ssh-autopilot] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
