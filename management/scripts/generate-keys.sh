#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${1:-.}"
KEYS_DIR="$PROJECT_ROOT/keys"

echo "🔑 Generating SSH keys for management roles..."

mkdir -p "$KEYS_DIR"

# Generate keys for each role
for ROLE in manager autopilot monitor; do
    ROLE_DIR="$KEYS_DIR/$ROLE"
    mkdir -p "$ROLE_DIR"

    if [ ! -f "$ROLE_DIR/id_ed25519" ]; then
        echo "  Generating key for: $ROLE"
        ssh-keygen \
            -t ed25519 \
            -f "$ROLE_DIR/id_ed25519" \
            -C "$ROLE@dockfra-management" \
            -N ""

        chmod 600 "$ROLE_DIR/id_ed25519"
        chmod 644 "$ROLE_DIR/id_ed25519.pub"
    else
        echo "  ⚠️  Key already exists for $ROLE (skipping)"
    fi
done

# Also generate legacy deployer key for backward compatibility
if [ ! -f "$KEYS_DIR/deployer" ]; then
    echo "  Generating legacy deployer key..."
    ssh-keygen -t ed25519 -f "$KEYS_DIR/deployer" -N "" -C "dockfra-deployer"
    chmod 600 "$KEYS_DIR/deployer"
    chmod 644 "$KEYS_DIR/deployer.pub"
fi

# Create SSH config for roles to reach developer
cat > "$KEYS_DIR/config" << 'EOF'
Host ssh-developer
    HostName ssh-developer
    User developer
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile=/dev/null

Host *
    AddKeysToAgent yes
EOF

chmod 644 "$KEYS_DIR/config"

echo "✅ SSH keys generated in: $KEYS_DIR"
