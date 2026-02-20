#!/bin/bash
set -e

echo "========================================="
echo "  Building ${APP_NAME} Desktop v${APP_VERSION}"
echo "  Target arch: ${RPI3_ARCH:-linux/arm/v7}"
echo "========================================="

DIST_DIR="/app/dist"
DOWNLOAD_DIR="/output/frontend/downloads"
mkdir -p "$DIST_DIR" "$DOWNLOAD_DIR"

# --- Build Linux x64 artifact ---
echo "[*] Building Linux x64 package..."
cd /app/src
tar czf "${DIST_DIR}/app-linux-x64.tar.gz" \
    --transform="s|^|${APP_NAME}-${APP_VERSION}/|" \
    *.py
echo "[✓] Linux x64 package ready"

# --- Build Linux ARM (RPi3) artifact ---
echo "[*] Building Linux ARM (RPi3) package..."
cat > "${DIST_DIR}/run-rpi3.sh" << 'LAUNCHER'
#!/bin/bash
# RPi3 launcher for desktop app
export DISPLAY=${DISPLAY:-:0}
cd "$(dirname "$0")"
echo "Starting ${APP_NAME} on RPi3..."
python3 main.py "$@"
LAUNCHER
chmod +x "${DIST_DIR}/run-rpi3.sh"

cd /app/src
tar czf "${DIST_DIR}/app-linux-arm.tar.gz" \
    --transform="s|^|${APP_NAME}-${APP_VERSION}/|" \
    *.py -C "${DIST_DIR}" run-rpi3.sh
echo "[✓] Linux ARM package ready"

# --- Create placeholder artifacts for other platforms ---
echo "[*] Creating placeholder packages..."
echo "Windows MSI placeholder — build with: cargo tauri build --target x86_64-pc-windows-msvc" \
    > "${DIST_DIR}/app-windows.msi"
echo "macOS DMG placeholder — build with: cargo tauri build --target aarch64-apple-darwin" \
    > "${DIST_DIR}/app-macos.dmg"

# --- Copy to frontend downloads directory ---
echo "[*] Publishing to frontend downloads..."
cp "${DIST_DIR}"/* "${DOWNLOAD_DIR}/" 2>/dev/null || true

echo ""
echo "========================================="
echo "  Build complete!"
echo "  Artifacts in: ${DIST_DIR}"
echo "  Published to: ${DOWNLOAD_DIR}"
echo "========================================="
ls -lah "${DIST_DIR}"/
