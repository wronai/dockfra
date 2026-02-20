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

# Fix ownership if files were created by a Docker container running as a different user
if [ ! -w "$DEV_KEYS" ] || { [ -f "$DEV_KEYS/authorized_keys" ] && [ ! -w "$DEV_KEYS/authorized_keys" ]; }; then
    echo "🔧 Fixing ownership of $DEV_KEYS (created by Docker)..."
    sudo chown -R "$(id -u):$(id -g)" "$DEV_KEYS" 2>/dev/null || \
    docker run --rm -v "$DEV_KEYS:/mnt" alpine chown -R "$(id -u):$(id -g)" /mnt 2>/dev/null || {
        echo "❌ Cannot fix ownership. Run: sudo chown -R $(whoami) $DEV_KEYS"
        exit 1
    }
fi

echo "📋 Syncing management public keys to developer..."

# Collect all management public keys into a temp file, then atomically replace
TMPFILE="$DEV_KEYS/.authorized_keys.tmp"
: > "$TMPFILE"

for ROLE in manager autopilot monitor; do
    PUB_KEY="$MGMT_ROOT/keys/$ROLE/id_ed25519.pub"
    if [ -f "$PUB_KEY" ]; then
        echo "  Adding $ROLE public key..."
        cat "$PUB_KEY" >> "$TMPFILE"
    fi
done

# Also add legacy deployer key if exists
if [ -f "$MGMT_ROOT/keys/deployer.pub" ]; then
    echo "  Adding deployer public key..."
    cat "$MGMT_ROOT/keys/deployer.pub" >> "$TMPFILE"
fi

chmod 600 "$TMPFILE"
mv -f "$TMPFILE" "$DEV_KEYS/authorized_keys"
echo "✅ Keys synced to: $DEV_KEYS/authorized_keys"
