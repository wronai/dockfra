#!/bin/bash
set -euo pipefail

MGMT_ROOT="$(dirname "$(dirname "${BASH_SOURCE[0]}")")"
APP_ROOT="$MGMT_ROOT/../app"
DEV_KEYS="$APP_ROOT/ssh-developer/keys"

if [ ! -d "$APP_ROOT" ]; then
    echo "⚠️  app directory not found at $APP_ROOT"
    exit 1
fi

mkdir -p "$DEV_KEYS"

echo "📋 Syncing management public keys to developer..."

# Collect all management public keys into authorized_keys
> "$DEV_KEYS/authorized_keys"

for ROLE in manager autopilot monitor; do
    PUB_KEY="$MGMT_ROOT/keys/$ROLE/id_ed25519.pub"
    if [ -f "$PUB_KEY" ]; then
        echo "  Adding $ROLE public key..."
        cat "$PUB_KEY" >> "$DEV_KEYS/authorized_keys"
    fi
done

# Also add legacy deployer key if exists
if [ -f "$MGMT_ROOT/keys/deployer.pub" ]; then
    echo "  Adding deployer public key..."
    cat "$MGMT_ROOT/keys/deployer.pub" >> "$DEV_KEYS/authorized_keys"
fi

chmod 600 "$DEV_KEYS/authorized_keys"
echo "✅ Keys synced to: $DEV_KEYS/authorized_keys"
