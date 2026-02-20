#!/bin/bash
# deploy.sh — Deploy artifacts to RPi3 via ssh-rpi3 container
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEVICES_ROOT="$(dirname "$SCRIPT_DIR")"
CONTAINER="${SSH_RPI3_CONTAINER:-dockfra-ssh-rpi3}"
ARTIFACT="${1:-}"
REMOTE_PATH="${2:-/home/pi/apps}"

echo "🚀 Deploying to RPi3 via $CONTAINER..."

if ! docker inspect "$CONTAINER" &>/dev/null; then
    echo "❌ Container $CONTAINER is not running."
    echo "   Start it first: make up-devices"
    exit 1
fi

if [ -z "$ARTIFACT" ]; then
    echo "Usage: deploy.sh <artifact-path> [remote-path]"
    echo ""
    echo "Available artifacts in container:"
    docker exec "$CONTAINER" ls -lah /artifacts/ 2>/dev/null || echo "  (none)"
    echo ""
    echo "Examples:"
    echo "  deploy.sh /artifacts/app.tar.gz /home/pi/apps"
    echo "  deploy.sh /artifacts/app.deb /tmp"
    exit 1
fi

echo "  Artifact:    $ARTIFACT"
echo "  Remote path: $REMOTE_PATH"
echo ""

docker exec "$CONTAINER" bash -c "/config/deploy/push-to-rpi3.sh '$ARTIFACT' '$REMOTE_PATH'"
echo "✅ Deploy complete"
