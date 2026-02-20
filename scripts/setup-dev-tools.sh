#!/bin/bash
# setup-dev-tools.sh — Install and configure LLM dev tools inside ssh-developer
set -euo pipefail

CONTAINER="${DEVELOPER_CONTAINER:-dockfra-ssh-developer}"
DEV_USER="${DEVELOPER_USER:-developer}"
LLM_MODEL="${LLM_MODEL:-google/gemini-3-flash-preview}"
LITELLM_PORT="${LITELLM_PORT:-4000}"

echo "🛠️  Setting up LLM dev tools in $CONTAINER..."

# Verify container is running
if ! docker inspect "$CONTAINER" &>/dev/null; then
    echo "❌ Container $CONTAINER is not running."
    exit 1
fi

# Load API key
OPENROUTER_API_KEY=""
if command -v getv &>/dev/null; then
    OPENROUTER_API_KEY=$(getv get llm openrouter OPENROUTER_API_KEY 2>/dev/null || true)
fi
if [ -z "$OPENROUTER_API_KEY" ] && [ -f "$HOME/.getv/llm/openrouter.env" ]; then
    OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' "$HOME/.getv/llm/openrouter.env" | cut -d= -f2-)
fi
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ OPENROUTER_API_KEY not found. Run: make setup-llm"
    exit 1
fi

# ─── 1. Continue.dev configuration ───────────────────────────────
echo ""
echo "📦 Configuring Continue.dev..."
docker exec "$CONTAINER" bash -c "
    mkdir -p /home/$DEV_USER/.continue
    cat > /home/$DEV_USER/.continue/config.json << EOF
{
  \"models\": [
    {
      \"title\": \"Gemini Flash (OpenRouter)\",
      \"provider\": \"openai\",
      \"model\": \"$LLM_MODEL\",
      \"apiBase\": \"https://openrouter.ai/api/v1\",
      \"apiKey\": \"$OPENROUTER_API_KEY\"
    }
  ],
  \"tabAutocompleteModel\": {
    \"title\": \"Gemini Flash Autocomplete\",
    \"provider\": \"openai\",
    \"model\": \"$LLM_MODEL\",
    \"apiBase\": \"https://openrouter.ai/api/v1\",
    \"apiKey\": \"$OPENROUTER_API_KEY\"
  },
  \"allowAnonymousTelemetry\": false,
  \"docs\": []
}
EOF
    chown -R $DEV_USER:$DEV_USER /home/$DEV_USER/.continue
"
echo "  ✅ Continue.dev config at ~/.continue/config.json"
echo "     → In VS Code/Windsurf: Remote-SSH to ssh-developer, Continue extension reads this config"

# ─── 2. Aider configuration ──────────────────────────────────────
echo ""
echo "📦 Configuring Aider..."
docker exec "$CONTAINER" bash -c "
    cat > /home/$DEV_USER/.aider.conf.yml << EOF
# Aider config — uses OpenRouter
openai-api-key: $OPENROUTER_API_KEY
openai-api-base: https://openrouter.ai/api/v1
model: openrouter/$LLM_MODEL
auto-commits: true
dark-mode: true
EOF
    chown $DEV_USER:$DEV_USER /home/$DEV_USER/.aider.conf.yml
"
echo "  ✅ Aider config at ~/.aider.conf.yml"
echo "     → SSH in and run: aider-start (or: aider --model openrouter/$LLM_MODEL)"

# ─── 3. Claude Code CLI setup ────────────────────────────────────
echo ""
echo "📦 Setting up Claude Code CLI compatibility..."
docker exec "$CONTAINER" bash -c "
    # Create a wrapper that routes claude through LiteLLM proxy
    cat > /home/$DEV_USER/scripts/claude-proxy << 'SCRIPT'
#!/bin/bash
# Claude Code CLI proxy — routes through LiteLLM (must run litellm-start first)
source ~/.llm-env 2>/dev/null
export ANTHROPIC_API_KEY=\"\$OPENROUTER_API_KEY\"
export ANTHROPIC_BASE_URL=\"http://localhost:4000\"
echo \"ℹ️  Claude Code routed through LiteLLM proxy (localhost:4000)\"
echo \"   Model: \$LLM_MODEL via OpenRouter\"
echo \"   Ensure LiteLLM is running: litellm-start\"
if command -v claude &>/dev/null; then
    exec claude \"\$@\"
else
    echo \"❌ Claude CLI not installed. Install: npm install -g @anthropic-ai/claude-code\"
    echo \"   Or use aider instead: aider-start\"
fi
SCRIPT
    chmod +x /home/$DEV_USER/scripts/claude-proxy
    chown $DEV_USER:$DEV_USER /home/$DEV_USER/scripts/claude-proxy
"
echo "  ✅ Claude proxy script at ~/scripts/claude-proxy"

# ─── 4. VS Code / Windsurf Remote SSH config ─────────────────────
echo ""
echo "📦 Generating VS Code Remote SSH config snippet..."
SSH_DEV_PORT=$(docker port "$CONTAINER" 2222 2>/dev/null | head -1 | cut -d: -f2 || echo "2200")
cat << EOF

  ── VS Code / Windsurf / Cursor Remote SSH ──

  Add to your local ~/.ssh/config:

    Host dockfra-developer
        HostName localhost
        Port ${SSH_DEV_PORT}
        User developer
        IdentityFile ~/.ssh/id_ed25519
        StrictHostKeyChecking no
        UserKnownHostsFile /dev/null

  Then in VS Code/Windsurf:
    1. Cmd+Shift+P → "Remote-SSH: Connect to Host" → dockfra-developer
    2. Install Continue extension on remote
    3. Continue reads ~/.continue/config.json automatically
    4. Prompt: "napraw DSI config" — edits files inside container

EOF

# ─── 5. Git credential helper for HTTPS (fallback) ───────────────
docker exec "$CONTAINER" bash -c "
    su - $DEV_USER -c 'git config --global credential.helper store'
"

echo "✅ Dev tools setup complete!"
echo ""
echo "  Available tools inside ssh-developer:"
echo "    aider-start       — AI pair programming (recommended)"
echo "    litellm-start     — Start LiteLLM proxy for Continue.dev/Claude"
echo "    llm-ask 'q'       — Quick LLM question"
echo "    claude-proxy      — Route Claude CLI through LiteLLM"
echo ""
echo "  IDE Remote SSH:"
echo "    VS Code:   Remote-SSH → dockfra-developer"
echo "    Windsurf:  Remote-SSH → dockfra-developer"
echo "    Cursor:    Remote-SSH → dockfra-developer"
