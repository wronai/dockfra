#!/bin/bash
set -e
echo "[ssh-monitor] Initializing monitor/deploy service..."
MH="/home/monitor"
mkdir -p "$MH/.ssh" /shared/tickets

[ -f /keys/deployer ] && { cp /keys/deployer "$MH/.ssh/id_rsa"; chmod 600 "$MH/.ssh/id_rsa"; }
[ -f /keys/deployer.pub ] && { cp /keys/deployer.pub "$MH/.ssh/authorized_keys"; chmod 600 "$MH/.ssh/authorized_keys"; }

cat > "$MH/.ssh/config" << EOF
Host ssh-developer
    HostName ${SSH_DEVELOPER_HOST:-ssh-developer}
    Port ${SSH_DEVELOPER_PORT:-2222}
    User developer
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
Host ssh-rpi3
    HostName ${SSH_RPI3_HOST:-ssh-rpi3}
    Port ${SSH_RPI3_PORT:-2222}
    User ${SSH_DEPLOY_USER:-deployer}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
EOF

chown -R monitor:monitor "$MH/.ssh"

[ ! -f "$MH/.service-env" ] && env | grep -E '^(OPENROUTER_|LLM_|SERVICE_ROLE|TICKETS_DIR|MONITOR_)' > "$MH/.service-env" 2>/dev/null || true
chown monitor:monitor "$MH/.service-env"

cat > "$MH/.bashrc" << 'RC'
[ -f ~/.service-env ] && export $(grep -v '^#' ~/.service-env | xargs) 2>/dev/null
export PYTHONPATH="/shared/lib:$PYTHONPATH"
export PATH="$HOME/deploy:$PATH"
alias ll='ls -lah'; alias status='~/deploy/status.sh'; alias deploy-all='~/deploy/deploy-all.sh'
alias llm='python3 /shared/lib/llm_client.py'; alias tickets='python3 /shared/lib/ticket_system.py'
alias monitor-log='tail -f /var/log/monitor-daemon.log'
[ -f /etc/motd ] && cat /etc/motd
RC
chown monitor:monitor "$MH/.bashrc"

# Track deployed commit
echo "none" > "$MH/.last-deployed-commit"
[ -d /repo/.git ] && (cd /repo && git rev-parse HEAD > "$MH/.last-deployed-commit" 2>/dev/null || true)
chown monitor:monitor "$MH/.last-deployed-commit"

touch /var/log/monitor-daemon.log && chown monitor:monitor /var/log/monitor-daemon.log

# Structured logging — startup event
mkdir -p /var/log/dockfra
python3 -c "
import json,os; from datetime import datetime,timezone
entry=json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'service':'monitor','level':'ACTION','message':'ssh-monitor started','data':{'env':os.environ.get('ENVIRONMENT','local')}})
open('/var/log/dockfra/decisions.jsonl','a').write(entry+'\n')
" 2>/dev/null || true

echo "[ssh-monitor] Starting monitor daemon..."
su - monitor -c "nohup /home/monitor/monitor-daemon.sh >> /var/log/monitor-daemon.log 2>&1 &"

echo "[ssh-monitor] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
