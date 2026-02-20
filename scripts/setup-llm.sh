#!/bin/bash
# setup-llm.sh — Configure LLM (OpenRouter via getv) inside ssh-developer
set -euo pipefail

CONTAINER="${DEVELOPER_CONTAINER:-dockfra-ssh-developer}"
DEV_USER="${DEVELOPER_USER:-developer}"
LLM_MODEL="${LLM_MODEL:-google/gemini-3-flash-preview}"

echo "🤖 Setting up LLM configuration in $CONTAINER..."

# Verify container is running
if ! docker inspect "$CONTAINER" &>/dev/null; then
    echo "❌ Container $CONTAINER is not running."
    echo "   Start it first: make up-app"
    exit 1
fi

# Get API key from getv
if command -v getv &>/dev/null; then
    OPENROUTER_API_KEY=$(getv get llm openrouter OPENROUTER_API_KEY 2>/dev/null || true)
fi

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    # Fallback: read from ~/.getv/llm/openrouter.env
    if [ -f "$HOME/.getv/llm/openrouter.env" ]; then
        OPENROUTER_API_KEY=$(grep '^OPENROUTER_API_KEY=' "$HOME/.getv/llm/openrouter.env" | cut -d= -f2-)
    fi
fi

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "❌ OPENROUTER_API_KEY not found."
    echo "   Set it with: getv set llm openrouter OPENROUTER_API_KEY=sk-or-v1-..."
    echo "   Or:          pip install getv && getv set llm openrouter OPENROUTER_API_KEY=your-key"
    exit 1
fi

echo "  📦 API Key: ${OPENROUTER_API_KEY:0:12}...${OPENROUTER_API_KEY: -4}"
echo "  📦 Model:   $LLM_MODEL"

# Inject LLM env vars into the container
docker exec "$CONTAINER" bash -c "
    cat > /home/$DEV_USER/.llm-env << EOF
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
LLM_MODEL=$LLM_MODEL
OPENAI_API_BASE=https://openrouter.ai/api/v1
OPENAI_API_KEY=$OPENROUTER_API_KEY
LITELLM_MODEL=$LLM_MODEL
EOF
    chmod 600 /home/$DEV_USER/.llm-env
    chown $DEV_USER:$DEV_USER /home/$DEV_USER/.llm-env
"

# Update .service-env with LLM config
docker exec "$CONTAINER" bash -c "
    # Remove old LLM entries
    sed -i '/^OPENROUTER_API_KEY=/d; /^LLM_MODEL=/d; /^OPENAI_API_BASE=/d; /^OPENAI_API_KEY=/d; /^LITELLM_MODEL=/d' /home/$DEV_USER/.service-env 2>/dev/null || true
    # Append new
    cat /home/$DEV_USER/.llm-env >> /home/$DEV_USER/.service-env
"

# Ensure .bashrc loads LLM env
docker exec "$CONTAINER" bash -c "
    if ! grep -q '.llm-env' /home/$DEV_USER/.bashrc 2>/dev/null; then
        echo '[ -f ~/.llm-env ] && export \$(grep -v \"^#\" ~/.llm-env | xargs) 2>/dev/null' >> /home/$DEV_USER/.bashrc
        chown $DEV_USER:$DEV_USER /home/$DEV_USER/.bashrc
    fi
"

echo "  ✅ LLM env vars injected"

# Install LiteLLM proxy inside container
echo ""
echo "📦 Installing LiteLLM + aider-chat..."
docker exec "$CONTAINER" bash -c "
    pip install --quiet litellm aider-chat 2>/dev/null || pip3 install --quiet litellm aider-chat 2>/dev/null || true
"
echo "  ✅ LiteLLM + aider installed"

# Create LiteLLM config
docker exec "$CONTAINER" bash -c "
    mkdir -p /home/$DEV_USER/.litellm
    cat > /home/$DEV_USER/.litellm/config.yaml << EOF
model_list:
  - model_name: default
    litellm_params:
      model: openrouter/$LLM_MODEL
      api_key: $OPENROUTER_API_KEY
      api_base: https://openrouter.ai/api/v1

  - model_name: gemini-flash
    litellm_params:
      model: openrouter/$LLM_MODEL
      api_key: $OPENROUTER_API_KEY

  - model_name: gpt-4o
    litellm_params:
      model: openrouter/openai/gpt-4o
      api_key: $OPENROUTER_API_KEY

litellm_settings:
  drop_params: true
  set_verbose: false
EOF
    chown -R $DEV_USER:$DEV_USER /home/$DEV_USER/.litellm
"
echo "  ✅ LiteLLM config at ~/.litellm/config.yaml"

# Create convenience scripts
docker exec "$CONTAINER" bash -c "
    mkdir -p /home/$DEV_USER/scripts

    # LiteLLM proxy start
    cat > /home/$DEV_USER/scripts/litellm-start << 'SCRIPT'
#!/bin/bash
source ~/.llm-env 2>/dev/null
echo \"Starting LiteLLM proxy on :4000 (model: \$LLM_MODEL)...\"
litellm --config ~/.litellm/config.yaml --port 4000 &
echo \"LiteLLM PID: \$!\"
echo \"  Base URL: http://localhost:4000\"
echo \"  Test: curl http://localhost:4000/health\"
SCRIPT

    # Aider launcher
    cat > /home/$DEV_USER/scripts/aider-start << 'SCRIPT'
#!/bin/bash
source ~/.llm-env 2>/dev/null
cd /repo 2>/dev/null || cd ~/workspace
echo \"Starting aider with \$LLM_MODEL via OpenRouter...\"
exec aider --model \"openrouter/\$LLM_MODEL\"
SCRIPT

    # Quick LLM ask
    cat > /home/$DEV_USER/scripts/llm-ask << 'SCRIPT'
#!/bin/bash
source ~/.llm-env 2>/dev/null
if [ -z \"\$1\" ]; then
    echo \"Usage: llm-ask 'your question'\"
    exit 1
fi
python3 /shared/lib/llm_client.py ask \"\$@\"
SCRIPT

    chmod +x /home/$DEV_USER/scripts/litellm-start
    chmod +x /home/$DEV_USER/scripts/aider-start
    chmod +x /home/$DEV_USER/scripts/llm-ask
    chown -R $DEV_USER:$DEV_USER /home/$DEV_USER/scripts
"
echo "  ✅ Helper scripts: litellm-start, aider-start, llm-ask"

echo ""
echo "✅ LLM setup complete!"
echo ""
echo "  Usage inside ssh-developer (make ssh-developer):"
echo "    litellm-start          # Start LiteLLM proxy on :4000"
echo "    aider-start            # Launch aider with OpenRouter"
echo "    llm-ask 'question'     # Quick LLM query"
echo "    echo \$LLM_MODEL        # Current model"
