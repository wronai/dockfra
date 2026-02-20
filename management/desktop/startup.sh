#!/bin/bash
set -e

W="${DISPLAY_WIDTH:-1280}"
H="${DISPLAY_HEIGHT:-720}"
VNC_PASS="${VNC_PASSWORD:-dockfra}"
DASHBOARD_URL="${DASHBOARD_URL:-http://host.docker.internal:5050/dashboard}"

echo "╔══════════════════════════════════════╗"
echo "║  Management Desktop                  ║"
echo "║  VNC → http://localhost:6081         ║"
echo "╚══════════════════════════════════════╝"

# SSH key
[ -f /keys/deployer ] && cp /keys/deployer /root/.ssh/id_rsa && chmod 600 /root/.ssh/id_rsa

# Start Xvfb
Xvfb :1 -screen 0 "${W}x${H}x24" &
export DISPLAY=:1
sleep 1

# Window manager
fluxbox &
sleep 1

# VNC password
mkdir -p /root/.vnc
x11vnc -storepasswd "$VNC_PASS" /root/.vnc/passwd

# Terminal with shortcuts
xterm -geometry 120x35+0+0 -title "Management Console" -bg '#0f1117' -fg '#e8eaf6' -e bash -c '
echo "═══════════════════════════════════════════════════"
echo "  Dockfra Management Desktop"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Dostępne komendy:"
echo "    dashboard      — Otwórz panel zarządzania"
echo "    dps            — Lista kontenerów"
echo "    dlogs NAME     — Logi kontenera"
echo ""
alias dashboard="chromium-browser --no-sandbox '"${DASHBOARD_URL}"' &"
alias dps="docker ps --format \"table {{.Names}}\t{{.Status}}\t{{.Ports}}\""
alias dlogs="docker logs -f"
exec bash
' &

# Open dashboard in Chromium after 2s
sleep 2
chromium-browser --no-sandbox \
    --disable-gpu \
    --window-size="${W},${H}" \
    --app="${DASHBOARD_URL}" \
    --disable-extensions \
    --disable-background-networking \
    2>/dev/null &

# x11vnc
x11vnc -display :1 -rfbauth /root/.vnc/passwd -forever -shared -bg -rfbport 5901

# noVNC
exec websockify --web /usr/share/novnc 6081 localhost:5901
