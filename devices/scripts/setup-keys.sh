#!/bin/bash
# setup-keys.sh — Copy SSH keys from app/management into devices stack
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVICES_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEVICES_ROOT")"
KEYS_DIR="$DEVICES_ROOT/keys"

mkdir -p "$KEYS_DIR"

echo "🔑 Setting up SSH keys for devices stack..."

# Try to find deployer key from management or app
DEPLOYER_KEY=""
for candidate in \
    "$PROJECT_ROOT/management/keys/deployer" \
    "$PROJECT_ROOT/app/ssh-developer/keys/deployer" \
    "$HOME/.ssh/id_ed25519"; do
    if [ -f "$candidate" ]; then
        DEPLOYER_KEY="$candidate"
        break
    fi
done

if [ -z "$DEPLOYER_KEY" ]; then
    echo "⚠️  No deployer key found. Generating new one..."
    ssh-keygen -t ed25519 -f "$KEYS_DIR/deployer" -N "" -C "dockfra-deployer"
    echo "✅ Generated: $KEYS_DIR/deployer"
else
    echo "  Found key: $DEPLOYER_KEY"
    cp "$DEPLOYER_KEY" "$KEYS_DIR/deployer"
    cp "${DEPLOYER_KEY}.pub" "$KEYS_DIR/deployer.pub" 2>/dev/null || \
        ssh-keygen -y -f "$DEPLOYER_KEY" > "$KEYS_DIR/deployer.pub"
    chmod 600 "$KEYS_DIR/deployer"
    chmod 644 "$KEYS_DIR/deployer.pub"
    echo "✅ Copied deployer key to $KEYS_DIR/"
fi

echo ""
echo "📋 To authorize this key on your RPi3, run:"
echo "   ssh-copy-id -i $KEYS_DIR/deployer.pub pi@<RPI3_HOST>"
echo "   or:"
echo "   cat $KEYS_DIR/deployer.pub | ssh pi@<RPI3_HOST> 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'"
