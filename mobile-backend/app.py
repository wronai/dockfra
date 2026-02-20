"""Mobile Backend API — lightweight API for mobile/desktop clients."""
import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request

APP_NAME = os.environ.get("APP_NAME", "InfraDemo")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_DEBUG = os.environ.get("APP_DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
DEPLOY_MODE = os.environ.get("DEPLOY_MODE", "local")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8081")

app = Flask(__name__)
app.secret_key = SECRET_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "mobile-backend",
        "version": APP_VERSION,
        "deploy_mode": DEPLOY_MODE,
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route("/config")
def config():
    """Return client configuration for mobile/desktop apps."""
    return jsonify({
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "api_base": BACKEND_URL,
        "features": {
            "push_notifications": True,
            "offline_mode": True,
            "sync_interval_seconds": 300
        },
        "min_client_version": "0.9.0"
    })


@app.route("/sync", methods=["POST"])
def sync():
    """Sync endpoint for mobile/desktop clients."""
    data = request.get_json(silent=True) or {}
    client_id = data.get("client_id", "unknown")
    last_sync = data.get("last_sync")
    logger.info(f"Sync request from client={client_id}, last_sync={last_sync}")
    return jsonify({
        "status": "ok",
        "server_time": datetime.utcnow().isoformat(),
        "updates": [],
        "next_sync_in": 300
    })


@app.route("/device/register", methods=["POST"])
def register_device():
    """Register a device (mobile/desktop/RPi3)."""
    data = request.get_json(silent=True) or {}
    return jsonify({
        "status": "registered",
        "device_id": data.get("device_id", "auto-generated"),
        "device_type": data.get("device_type", "unknown"),
        "registered_at": datetime.utcnow().isoformat()
    })


if __name__ == "__main__":
    port = int(os.environ.get("MOBILE_BACKEND_PORT", 8082))
    logger.info(f"Starting mobile-backend v{APP_VERSION} on port {port}")
    app.run(host="0.0.0.0", port=port, debug=APP_DEBUG)
