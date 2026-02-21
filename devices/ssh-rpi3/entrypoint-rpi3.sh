#!/bin/bash
# 10-rpi3-setup.sh — Custom initialization for RPi3 deploy channel

echo "[ssh-rpi3] Initializing RPi3 deploy channel..."
echo "[ssh-rpi3] Target RPi3: ${RPI3_HOST:-not-configured}:${RPI3_SSH_PORT:-22}"
echo "[ssh-rpi3] Deploy user: ${SSH_DEPLOY_USER:-deployer}"

# Setup SSH keys for connecting to actual RPi3
SSH_DIR="/config/.ssh"
mkdir -p "$SSH_DIR"

if [ -f /keys/deployer ]; then
    cp /keys/deployer "$SSH_DIR/id_rsa"
    chmod 600 "$SSH_DIR/id_rsa"
    echo "[ssh-rpi3] SSH key configured for RPi3 access"
fi

# Setup known_hosts (disable strict checking for internal use)
cat > "$SSH_DIR/config" << EOF
Host rpi3
    HostName ${RPI3_HOST:-127.0.0.1}
    Port ${RPI3_SSH_PORT:-22}
    User ${RPI3_USER:-pi}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
EOF

# Create deploy helper scripts
DEPLOY_DIR="/config/deploy"
mkdir -p "$DEPLOY_DIR"

cat > "$DEPLOY_DIR/push-to-rpi3.sh" << 'SCRIPT'
#!/bin/bash
# Push artifacts to RPi3
ARTIFACT=$1
REMOTE_PATH="${2:-/home/pi/apps}"

if [ -z "$ARTIFACT" ]; then
    echo "Usage: push-to-rpi3.sh <artifact-path> [remote-path]"
    echo "Available artifacts:"
    ls -lah /artifacts/ 2>/dev/null || echo "  (none)"
    exit 1
fi

echo "[push] Sending ${ARTIFACT} to RPi3:${REMOTE_PATH}..."
scp -F /config/.ssh/config "$ARTIFACT" "rpi3:${REMOTE_PATH}/"
echo "[push] Done"
SCRIPT

cat > "$DEPLOY_DIR/run-on-rpi3.sh" << 'SCRIPT'
#!/bin/bash
# Execute command on RPi3
echo "[rpi3-exec] Running: $@"
ssh -F /config/.ssh/config rpi3 "$@"
SCRIPT

chmod +x "$DEPLOY_DIR"/*.sh

# Setup public key for incoming connections
if [ -f /keys/deployer.pub ]; then
    mkdir -p /config/.ssh
    cp /keys/deployer.pub "/config/.ssh/authorized_keys"
    echo "[ssh-rpi3] Authorized keys configured"
fi

# Seed default web content (shared volume with web-rpi3 nginx)
WWW_DIR="/var/www/html"
APPS_DIR="/home/deployer/apps"
mkdir -p "$WWW_DIR" "$APPS_DIR" 2>/dev/null
if [ ! -f "$WWW_DIR/index.html" ]; then
    cat > "$WWW_DIR/index.html" << 'HTML'
<!DOCTYPE html><html><head><meta charset="utf-8"><title>RPi3</title>
<style>body{font-family:sans-serif;background:#1a1a2e;color:#e0e0e0;text-align:center;padding:40px}
h1{color:#60a5fa}code{background:#2d2d44;padding:2px 8px;border-radius:4px}</style></head>
<body><h1>🍓 RPi3 Device</h1><p>Managed by <code>ssh-monitor</code></p>
<p><a href="/health" style="color:#60a5fa">/health</a> · <a href="/api/status" style="color:#60a5fa">/api/status</a></p></body></html>
HTML
    echo "[ssh-rpi3] Default web content created"
fi

# Create deploy-to-web helper (copies artifacts to nginx root)
cat > "$DEPLOY_DIR/deploy-web.sh" << 'SCRIPT'
#!/bin/bash
# Deploy artifact to web server
SRC="${1:?Usage: deploy-web.sh <source-dir-or-file>}"
echo "[deploy] Deploying $SRC to /var/www/html..."
cp -r "$SRC" /var/www/html/ 2>/dev/null || rsync -a "$SRC/" /var/www/html/
echo "[deploy] Web deployment complete"
echo "[deploy] Verify: curl http://web-rpi3:80/health"
SCRIPT
chmod +x "$DEPLOY_DIR/deploy-web.sh"

echo "[ssh-rpi3] RPi3 deploy channel ready"
echo "[ssh-rpi3] Available commands:"
echo "  push-to-rpi3.sh <artifact>  — Send file to RPi3"
echo "  run-on-rpi3.sh <command>    — Execute on RPi3"
echo "  deploy-web.sh <dir>         — Deploy to web server"
