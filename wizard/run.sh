#!/bin/bash
# Run the Dockfra Setup Wizard
set -euo pipefail
WIZARD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create venv if needed
if [ ! -f "$WIZARD_DIR/.venv/bin/python" ]; then
    echo "📦 Creating Python venv..."
    python3 -m venv "$WIZARD_DIR/.venv"
    "$WIZARD_DIR/.venv/bin/pip" install -q flask flask-socketio
fi

echo "🧙 Starting Dockfra Wizard → http://localhost:5050"
exec "$WIZARD_DIR/.venv/bin/python" "$WIZARD_DIR/app.py"
