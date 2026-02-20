#!/bin/bash
# setup-github-keys.sh — Copy host GitHub SSH keys + git config into ssh-developer container
set -euo pipefail

CONTAINER="${DEVELOPER_CONTAINER:-dockfra-ssh-developer}"
DEV_USER="${DEVELOPER_USER:-developer}"
SSH_KEY="${GITHUB_SSH_KEY:-$HOME/.ssh/id_ed25519}"
SSH_PUB="${SSH_KEY}.pub"

echo "🔑 Copying GitHub credentials to $CONTAINER..."

# Verify container is running
if ! docker inspect "$CONTAINER" &>/dev/null; then
    echo "❌ Container $CONTAINER is not running."
    echo "   Start it first: make up-app"
    exit 1
fi

# Verify SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found: $SSH_KEY"
    echo "   Set GITHUB_SSH_KEY to your GitHub key path."
    exit 1
fi

# Copy SSH private key
docker cp "$SSH_KEY" "$CONTAINER:/tmp/github_key"
docker exec "$CONTAINER" bash -c "
    mkdir -p /home/$DEV_USER/.ssh
    cp /tmp/github_key /home/$DEV_USER/.ssh/id_ed25519
    chmod 600 /home/$DEV_USER/.ssh/id_ed25519
    chown $DEV_USER:$DEV_USER /home/$DEV_USER/.ssh/id_ed25519
    rm /tmp/github_key
"
echo "  ✅ SSH private key copied"

# Copy SSH public key
if [ -f "$SSH_PUB" ]; then
    docker cp "$SSH_PUB" "$CONTAINER:/tmp/github_key.pub"
    docker exec "$CONTAINER" bash -c "
        cp /tmp/github_key.pub /home/$DEV_USER/.ssh/id_ed25519.pub
        chmod 644 /home/$DEV_USER/.ssh/id_ed25519.pub
        chown $DEV_USER:$DEV_USER /home/$DEV_USER/.ssh/id_ed25519.pub
        rm /tmp/github_key.pub
    "
    echo "  ✅ SSH public key copied"
fi

# Configure SSH for GitHub
docker exec "$CONTAINER" bash -c "
    cat > /home/$DEV_USER/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking accept-new

Host *
    AddKeysToAgent yes
EOF
    chmod 600 /home/$DEV_USER/.ssh/config
    chown $DEV_USER:$DEV_USER /home/$DEV_USER/.ssh/config
"
echo "  ✅ SSH config for github.com"

# Copy git config (user.name, user.email)
GIT_NAME=$(git config --global user.name 2>/dev/null || echo "developer")
GIT_EMAIL=$(git config --global user.email 2>/dev/null || echo "dev@local")

docker exec "$CONTAINER" su - "$DEV_USER" -c "
    git config --global user.name '$GIT_NAME'
    git config --global user.email '$GIT_EMAIL'
    git config --global init.defaultBranch main
    git config --global push.autoSetupRemote true
"
echo "  ✅ Git config: $GIT_NAME <$GIT_EMAIL>"

# Test GitHub SSH access
echo ""
echo "🧪 Testing GitHub SSH access..."
if docker exec "$CONTAINER" su - "$DEV_USER" -c "ssh -T git@github.com -o ConnectTimeout=10 2>&1" | grep -qi "success\|authenticated\|Hi "; then
    echo "  ✅ GitHub SSH authentication works!"
else
    echo "  ⚠️  GitHub SSH test inconclusive (may still work — check manually)"
    echo "     Run: make ssh-developer"
    echo "     Then: ssh -T git@github.com"
fi

echo ""
echo "✅ GitHub credentials injected into $CONTAINER"
echo "   SSH into developer: make ssh-developer"
echo "   Test:  ssh -T git@github.com"
echo "   Clone: git clone git@github.com:user/repo.git"
