#!/bin/bash
# inject-getv-env.sh — Inject getv profile env vars into a running container
set -euo pipefail

CONTAINER="${1:-dockfra-ssh-developer}"
DEV_USER="${DEVELOPER_USER:-developer}"
CATEGORY="${2:-llm}"
PROFILE="${3:-openrouter}"

echo "💉 Injecting getv $CATEGORY/$PROFILE into $CONTAINER..."

if ! docker inspect "$CONTAINER" &>/dev/null; then
    echo "❌ Container $CONTAINER is not running."
    exit 1
fi

# Export vars from getv profile
if command -v getv &>/dev/null; then
    ENV_VARS=$(getv export "$CATEGORY" "$PROFILE" --format shell 2>/dev/null || true)
else
    # Fallback: read .env file directly
    ENV_FILE="$HOME/.getv/$CATEGORY/$PROFILE.env"
    if [ -f "$ENV_FILE" ]; then
        ENV_VARS=""
        while IFS='=' read -r key value; do
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ "$key" =~ ^_.*$ ]] && continue
            [ -z "$key" ] && continue
            ENV_VARS="$ENV_VARS\nexport $key='$value'"
        done < "$ENV_FILE"
    else
        echo "❌ Profile not found: $ENV_FILE"
        echo "   Install getv: pip install getv"
        echo "   Or set vars:  getv set $CATEGORY $PROFILE KEY=value"
        exit 1
    fi
fi

if [ -z "$ENV_VARS" ]; then
    echo "❌ No variables found in $CATEGORY/$PROFILE"
    exit 1
fi

# Write env to container
docker exec "$CONTAINER" bash -c "
    cat > /home/$DEV_USER/.getv-$CATEGORY-$PROFILE.env << 'ENVEOF'
$(echo -e "$ENV_VARS" | sed 's/^export //')
ENVEOF
    chmod 600 /home/$DEV_USER/.getv-$CATEGORY-$PROFILE.env
    chown $DEV_USER:$DEV_USER /home/$DEV_USER/.getv-$CATEGORY-$PROFILE.env
"

echo "  ✅ Injected $CATEGORY/$PROFILE into $CONTAINER"
