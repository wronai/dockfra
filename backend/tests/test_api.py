"""Backend API tests."""
import os
import sys
import json
import pytest

# Ensure app module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test env vars before importing app
os.environ.setdefault("APP_NAME", "TestApp")
os.environ.setdefault("APP_VERSION", "0.0.1-test")
os.environ.setdefault("DEPLOY_MODE", "local")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("REDIS_HOST", "localhost")

from app import app


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHealthEndpoints:
    """Health check endpoint tests."""

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "backend"

    def test_health_has_version(self, client):
        r = client.get("/health")
        data = r.get_json()
        assert "version" in data
        assert data["version"] == "0.0.1-test"

    def test_health_has_deploy_mode(self, client):
        r = client.get("/health")
        data = r.get_json()
        assert data["deploy_mode"] == "local"

    def test_health_has_timestamp(self, client):
        r = client.get("/health")
        data = r.get_json()
        assert "timestamp" in data


class TestInfoEndpoint:
    """Info endpoint tests."""

    def test_info_returns_200(self, client):
        r = client.get("/info")
        assert r.status_code == 200

    def test_info_has_services(self, client):
        r = client.get("/info")
        data = r.get_json()
        assert "services" in data
        assert "db" in data["services"]
        assert "redis" in data["services"]


class TestEchoEndpoint:
    """Echo endpoint tests."""

    def test_echo_post(self, client):
        payload = {"message": "hello", "number": 42}
        r = client.post("/api/echo",
                        data=json.dumps(payload),
                        content_type="application/json")
        assert r.status_code == 200
        data = r.get_json()
        assert data["echo"] == payload

    def test_echo_empty_post(self, client):
        r = client.post("/api/echo", content_type="application/json")
        assert r.status_code == 200


class TestDBStatusEndpoint:
    """DB status tests (may fail without real DB)."""

    def test_db_status_returns_response(self, client):
        r = client.get("/db-status")
        # 200 or 503 depending on DB availability
        assert r.status_code in (200, 503)
        data = r.get_json()
        assert "status" in data
        assert data["service"] == "postgresql"


class TestRedisStatusEndpoint:
    """Redis status tests (may fail without real Redis)."""

    def test_redis_status_returns_response(self, client):
        r = client.get("/redis-status")
        assert r.status_code in (200, 503)
        data = r.get_json()
        assert "status" in data
        assert data["service"] == "redis"
