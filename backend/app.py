"""Backend API - Flask application with health checks and service monitoring."""
import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request
import psycopg2
import redis

# --- Config from ENV ---
APP_NAME = os.environ.get("APP_NAME", "InfraDemo")
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
APP_DEBUG = os.environ.get("APP_DEBUG", "false").lower() == "true"
APP_LOG_LEVEL = os.environ.get("APP_LOG_LEVEL", "info")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
DEPLOY_MODE = os.environ.get("DEPLOY_MODE", "local")

DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_USER = os.environ.get("DB_USER", "appuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "securepass123")
DB_NAME = os.environ.get("DB_NAME", "maindb")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "redispass123")

# --- App ---
app = Flask(__name__)
app.secret_key = SECRET_KEY

logging.basicConfig(
    level=getattr(logging, APP_LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_conn():
    """Get PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASSWORD,
        dbname=DB_NAME, connect_timeout=5
    )


def get_redis_conn():
    """Get Redis connection."""
    return redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASSWORD, decode_responses=True,
        socket_timeout=5
    )


@app.route("/health")
def health():
    """Main health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "backend",
        "version": APP_VERSION,
        "app_name": APP_NAME,
        "deploy_mode": DEPLOY_MODE,
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route("/db-status")
def db_status():
    """PostgreSQL health check."""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({"status": "ok", "service": "postgresql", "version": version})
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return jsonify({"status": "error", "service": "postgresql", "error": str(e)}), 503


@app.route("/redis-status")
def redis_status():
    """Redis health check."""
    try:
        r = get_redis_conn()
        info = r.info("server")
        return jsonify({
            "status": "ok", "service": "redis",
            "version": info.get("redis_version", "unknown")
        })
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return jsonify({"status": "error", "service": "redis", "error": str(e)}), 503


@app.route("/info")
def info():
    """System info endpoint."""
    return jsonify({
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "deploy_mode": DEPLOY_MODE,
        "debug": APP_DEBUG,
        "services": {
            "db": {"host": DB_HOST, "port": DB_PORT, "database": DB_NAME},
            "redis": {"host": REDIS_HOST, "port": REDIS_PORT},
        }
    })


@app.route("/api/echo", methods=["POST"])
def echo():
    """Echo endpoint for testing."""
    data = request.get_json(silent=True) or {}
    return jsonify({"echo": data, "timestamp": datetime.utcnow().isoformat()})


# --- Init DB tables on first request ---
@app.before_request
def init_db():
    """Initialize DB tables if not exists (runs once)."""
    if not hasattr(app, '_db_initialized'):
        try:
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    id SERIAL PRIMARY KEY,
                    service VARCHAR(100) NOT NULL,
                    version VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'deployed',
                    deployed_at TIMESTAMP DEFAULT NOW(),
                    metadata JSONB
                );
            """)
            conn.commit()
            cur.close()
            conn.close()
            app._db_initialized = True
            logger.info("Database tables initialized")
        except Exception as e:
            logger.warning(f"DB init skipped: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", 8081))
    logger.info(f"Starting {APP_NAME} backend v{APP_VERSION} on port {port} (mode={DEPLOY_MODE})")
    app.run(host="0.0.0.0", port=port, debug=APP_DEBUG)
