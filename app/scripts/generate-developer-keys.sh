#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${1:-.}"
DEV_KEYS="$PROJECT_ROOT/ssh-developer/keys"

mkdir -p "$DEV_KEYS"

echo "🔑 Generating developer SSH key..."

if [ ! -f "$DEV_KEYS/id_ed25519" ]; then
    ssh-keygen \
        -t ed25519 \
        -f "$DEV_KEYS/id_ed25519" \
        -C "developer@dockfra-app" \
        -N ""

    chmod 600 "$DEV_KEYS/id_ed25519"
    chmod 644 "$DEV_KEYS/id_ed25519.pub"

    echo "✅ Developer SSH key generated"
else
    echo "⚠️  Developer SSH key already exists"
fi

# Also generate legacy deployer key for backward compatibility
if [ ! -f "$DEV_KEYS/deployer" ]; then
    ssh-keygen -t ed25519 -f "$DEV_KEYS/deployer" -N "" -C "dockfra-deployer"
    chmod 600 "$DEV_KEYS/deployer"
    chmod 644 "$DEV_KEYS/deployer.pub"
fi

# Create empty authorized_keys (will be populated from management)
touch "$DEV_KEYS/authorized_keys"
chmod 600 "$DEV_KEYS/authorized_keys"

echo "✅ Developer keys ready in: $DEV_KEYS"
