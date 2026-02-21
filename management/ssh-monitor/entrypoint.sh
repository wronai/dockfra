#!/bin/bash
set -e
SSH_USER="monitor"
source /ssh-base-init.sh

# ── Monitor-specific: SSH client config ──────────────────────
cat > "$UH/.ssh/config" << EOF
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
chown -R monitor:monitor "$UH/.ssh" 2>/dev/null || true

# Monitor aliases (appended to base .bashrc)
cat >> "$UH/.bashrc" << 'RC'
alias status='~/scripts/status.sh'; alias deploy-all='~/scripts/deploy-all.sh'
alias monitor-log='tail -f /var/log/monitor-daemon.log'
RC

# Track deployed commit
echo "none" > "$UH/.last-deployed-commit"
[ -d /repo/.git ] && (cd /repo && git rev-parse HEAD > "$UH/.last-deployed-commit" 2>/dev/null || true)
chown monitor:monitor "$UH/.last-deployed-commit"

# Structured logging — startup event
touch /var/log/monitor-daemon.log && chown monitor:monitor /var/log/monitor-daemon.log
mkdir -p /var/log/dockfra
python3 -c "
import json,os; from datetime import datetime,timezone
entry=json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'service':'monitor','level':'ACTION','message':'ssh-monitor started','data':{'env':os.environ.get('ENVIRONMENT','local')}})
open('/var/log/dockfra/decisions.jsonl','a').write(entry+'\n')
" 2>/dev/null || true

# Start monitor daemon
echo "[ssh-monitor] Starting monitor daemon..."
su - monitor -c "nohup /home/monitor/monitor-daemon.sh >> /var/log/monitor-daemon.log 2>&1 &"

echo "[ssh-monitor] Starting SSH :2222..."
exec /usr/sbin/sshd -D -e
