#!/bin/bash
set -e

WIDTH="${DISPLAY_WIDTH:-1280}"
HEIGHT="${DISPLAY_HEIGHT:-720}"
VNC_PASS="${VNC_PASSWORD:-rpi3vnc}"
RPI3="${RPI3_HOST:-127.0.0.1}"
RPI3_PORT="${RPI3_SSH_PORT:-22}"
RPI3_USR="${RPI3_USER:-pi}"

echo "╔══════════════════════════════════════════╗"
echo "║  VNC-RPI3 Visual Access                  ║"
echo "║  Resolution: ${WIDTH}x${HEIGHT}          ║"
echo "║  RPi3 Target: ${RPI3}:${RPI3_PORT}       ║"
echo "║  Web VNC: http://localhost:6080          ║"
echo "╚══════════════════════════════════════════╝"

# --- Setup SSH key ---
if [ -f /keys/deployer ]; then
    cp /keys/deployer /root/.ssh/id_rsa
    chmod 600 /root/.ssh/id_rsa
    echo "[vnc] SSH key loaded"
fi

# --- Start virtual display ---
echo "[vnc] Starting Xvfb (${WIDTH}x${HEIGHT})..."
Xvfb :0 -screen 0 "${WIDTH}x${HEIGHT}x24" &
export DISPLAY=:0
sleep 1

# --- Start window manager ---
echo "[vnc] Starting Fluxbox..."
fluxbox &
sleep 1

# --- Set VNC password ---
mkdir -p /root/.vnc
x11vnc -storepasswd "$VNC_PASS" /root/.vnc/passwd

# --- Start info terminal ---
xterm -geometry 100x30+10+10 -title "RPi3 Connection" -e bash -c '
echo "═══════════════════════════════════════════"
echo "  VNC-RPI3 Visual Terminal"
echo "═══════════════════════════════════════════"
echo ""
echo "  Available commands:"
echo "    ssh-rpi3        — Connect to RPi3 via SSH"
echo "    check-rpi3      — Check RPi3 status"
echo "    vnc-forward      — Forward RPi3 VNC display"
echo ""

# Aliases
alias ssh-rpi3="ssh -p '"${RPI3_PORT}"' '"${RPI3_USR}"'@'"${RPI3}"'"
alias check-rpi3="ssh -p '"${RPI3_PORT}"' '"${RPI3_USR}"'@'"${RPI3}"' uname -a 2>/dev/null || echo RPi3 unreachable"

echo "Trying to reach RPi3..."
ssh -o ConnectTimeout=5 -p '"${RPI3_PORT}"' '"${RPI3_USR}"'@'"${RPI3}"' "echo Connected to RPi3: \$(hostname)" 2>/dev/null || \
    echo "[!] RPi3 not reachable (expected in local mode)"
echo ""
exec bash
' &

# --- Start x11vnc ---
echo "[vnc] Starting x11vnc..."
x11vnc -display :0 -rfbauth /root/.vnc/passwd -forever -shared -bg

# --- Start noVNC web server ---
echo "[vnc] Starting noVNC on :6080..."
websockify --web /usr/share/novnc 6080 localhost:5900
