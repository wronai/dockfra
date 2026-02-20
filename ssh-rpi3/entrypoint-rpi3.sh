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

echo "[ssh-rpi3] RPi3 deploy channel ready"
echo "[ssh-rpi3] Available commands:"
echo "  push-to-rpi3.sh <artifact>  — Send file to RPi3"
echo "  run-on-rpi3.sh <command>    — Execute on RPi3"
