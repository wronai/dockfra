"""
E2E tests for Dockfra Wizard API endpoints.

Tests ticket CRUD, stats, health, history, containers, and sync endpoints.
Run: pytest tests/test_e2e.py -v
"""
import json
import os
import shutil
import tempfile
import pytest
import sys

# Ensure dockfra package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tickets_dir(tmp_path_factory):
    """Create a temp tickets dir and point dockfra.tickets at it."""
    d = tmp_path_factory.mktemp("tickets")
    os.environ["TICKETS_DIR"] = str(d)
    return d


@pytest.fixture(scope="session")
def app_client(tickets_dir):
    """Create Flask test client — imports dockfra.app to register all routes."""
    os.environ["TICKETS_DIR"] = str(tickets_dir)
    os.environ.setdefault("DOCKFRA_ROOT", os.path.join(os.path.dirname(__file__), ".."))

    # Import app module (registers all @app.route endpoints)
    from dockfra.app import app as flask_app
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_tickets(tickets_dir):
    """Clean tickets dir before each test."""
    for f in tickets_dir.glob("T-*.json"):
        f.unlink()
    yield


# ── Ticket module unit tests ─────────────────────────────────────────────────

class TestTicketsModule:
    """Test dockfra.tickets module directly."""

    def test_create_ticket(self, tickets_dir):
        from dockfra import tickets
        t = tickets.create("Test ticket", description="desc", priority="high")
        assert t["id"] == "T-0001"
        assert t["title"] == "Test ticket"
        assert t["priority"] == "high"
        assert t["status"] == "open"
        assert (tickets_dir / "T-0001.json").exists()

    def test_get_ticket(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Get me")
        t = tickets.get("T-0001")
        assert t is not None
        assert t["title"] == "Get me"

    def test_get_missing(self, tickets_dir):
        from dockfra import tickets
        assert tickets.get("T-9999") is None

    def test_update_ticket(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Update me")
        t = tickets.update("T-0001", status="in_progress", priority="critical")
        assert t["status"] == "in_progress"
        assert t["priority"] == "critical"
        # Verify persisted
        t2 = tickets.get("T-0001")
        assert t2["status"] == "in_progress"

    def test_update_protected_fields(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Protected")
        t = tickets.update("T-0001", id="T-HACK", created_by="hacker")
        # id and created_by should NOT be changed
        assert t["id"] == "T-0001"
        assert t["created_by"] == "manager"

    def test_add_comment(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Comment me")
        t = tickets.add_comment("T-0001", "tester", "This is a comment")
        assert len(t["comments"]) == 1
        assert t["comments"][0]["author"] == "tester"
        assert t["comments"][0]["text"] == "This is a comment"

    def test_list_tickets(self, tickets_dir):
        from dockfra import tickets
        tickets.create("A", priority="high")
        tickets.create("B", priority="low")
        tickets.create("C", priority="high", assigned_to="monitor")
        all_t = tickets.list_tickets()
        assert len(all_t) == 3
        high = tickets.list_tickets(priority="high")
        assert len(high) == 2
        monitor = tickets.list_tickets(assigned_to="monitor")
        assert len(monitor) == 1

    def test_close_ticket(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Close me")
        t = tickets.close("T-0001")
        assert t["status"] == "closed"

    def test_auto_increment_ids(self, tickets_dir):
        from dockfra import tickets
        t1 = tickets.create("First")
        t2 = tickets.create("Second")
        t3 = tickets.create("Third")
        assert t1["id"] == "T-0001"
        assert t2["id"] == "T-0002"
        assert t3["id"] == "T-0003"

    def test_stats(self, tickets_dir):
        from dockfra import tickets
        tickets.create("A", priority="high")
        tickets.create("B", priority="low")
        tickets.update("T-0001", status="in_progress")
        s = tickets.stats()
        assert s["total"] == 2
        assert s["by_status"]["open"] == 1
        assert s["by_status"]["in_progress"] == 1
        assert s["by_priority"]["high"] == 1
        assert s["by_priority"]["low"] == 1

    def test_format_ticket(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Format me", priority="critical")
        t = tickets.get("T-0001")
        line = tickets.format_ticket(t)
        assert "T-0001" in line
        assert "Format me" in line
        assert "🔴" in line

    def test_format_ticket_verbose(self, tickets_dir):
        from dockfra import tickets
        tickets.create("Verbose", description="Some long description")
        t = tickets.get("T-0001")
        line = tickets.format_ticket(t, verbose=True)
        assert "Status:" in line
        assert "Some long" in line

    def test_sync_all_no_integrations(self, tickets_dir):
        from dockfra import tickets
        results = tickets.sync_all()
        assert results == {}

    def test_reload_env(self, tickets_dir):
        from dockfra import tickets
        os.environ["GITHUB_TOKEN"] = "test-token-123"
        os.environ["GITHUB_REPO"] = "test/repo"
        tickets.reload_env()
        assert tickets.GITHUB_TOKEN == "test-token-123"
        assert tickets.GITHUB_REPO == "test/repo"
        # Clean up
        del os.environ["GITHUB_TOKEN"]
        del os.environ["GITHUB_REPO"]
        tickets.reload_env()


# ── API endpoint tests ───────────────────────────────────────────────────────

class TestTicketsAPI:
    """Test /api/tickets/* endpoints."""

    def test_list_empty(self, app_client):
        r = app_client.get("/api/tickets")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data == []

    def test_create_ticket(self, app_client):
        r = app_client.post("/api/tickets", json={"title": "API ticket", "priority": "high"})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data["ticket"]["title"] == "API ticket"
        assert data["ticket"]["priority"] == "high"
        assert data["ticket"]["id"] == "T-0001"

    def test_create_ticket_no_title(self, app_client):
        r = app_client.post("/api/tickets", json={"description": "no title"})
        assert r.status_code == 400
        data = json.loads(r.data)
        assert data["ok"] is False

    def test_get_ticket(self, app_client):
        app_client.post("/api/tickets", json={"title": "Get this"})
        r = app_client.get("/api/tickets/T-0001")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["title"] == "Get this"

    def test_get_ticket_not_found(self, app_client):
        r = app_client.get("/api/tickets/T-9999")
        assert r.status_code == 404

    def test_update_ticket(self, app_client):
        app_client.post("/api/tickets", json={"title": "Update this"})
        r = app_client.put("/api/tickets/T-0001", json={"status": "in_progress"})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data["ticket"]["status"] == "in_progress"

    def test_update_ticket_not_found(self, app_client):
        r = app_client.put("/api/tickets/T-9999", json={"status": "closed"})
        assert r.status_code == 404

    def test_add_comment(self, app_client):
        app_client.post("/api/tickets", json={"title": "Comment this"})
        r = app_client.post("/api/tickets/T-0001/comment", json={
            "author": "tester", "text": "Great work!"
        })
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert len(data["ticket"]["comments"]) == 1

    def test_add_comment_empty_text(self, app_client):
        app_client.post("/api/tickets", json={"title": "No comment"})
        r = app_client.post("/api/tickets/T-0001/comment", json={"text": ""})
        assert r.status_code == 400

    def test_add_comment_not_found(self, app_client):
        r = app_client.post("/api/tickets/T-9999/comment", json={"text": "Hello"})
        assert r.status_code == 404

    def test_list_with_filters(self, app_client):
        app_client.post("/api/tickets", json={"title": "A", "priority": "high"})
        app_client.post("/api/tickets", json={"title": "B", "priority": "low"})
        app_client.post("/api/tickets", json={"title": "C", "assigned_to": "monitor"})

        r = app_client.get("/api/tickets?priority=high")
        data = json.loads(r.data)
        assert len(data) == 1
        assert data[0]["title"] == "A"

        r = app_client.get("/api/tickets?assigned_to=monitor")
        data = json.loads(r.data)
        assert len(data) == 1
        assert data[0]["title"] == "C"


class TestStatsAPI:
    """Test /api/stats endpoint."""

    def test_stats_empty(self, app_client):
        r = app_client.get("/api/stats")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "tickets" in data
        assert data["tickets"]["total"] == 0
        assert "containers" in data
        assert "suggestions" in data

    def test_stats_with_tickets(self, app_client):
        app_client.post("/api/tickets", json={"title": "A", "priority": "high"})
        app_client.post("/api/tickets", json={"title": "B", "priority": "low"})
        r = app_client.get("/api/stats")
        data = json.loads(r.data)
        assert data["tickets"]["total"] == 2
        assert data["tickets"]["by_priority"]["high"] == 1
        assert data["tickets"]["by_priority"]["low"] == 1

    def test_stats_suggestions_for_empty_project(self, app_client):
        r = app_client.get("/api/stats")
        data = json.loads(r.data)
        actions = [s["action"] for s in data["suggestions"]]
        assert "ticket_create_wizard" in actions

    def test_stats_integrations_structure(self, app_client):
        r = app_client.get("/api/stats")
        data = json.loads(r.data)
        assert "integrations" in data
        for key in ("github", "jira", "trello", "linear"):
            assert key in data["integrations"]


class TestHealthAPI:
    """Test /api/health endpoint."""

    def test_health_returns_json(self, app_client):
        r = app_client.get("/api/health")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "ok" in data
        assert "running" in data
        assert "failing" in data
        assert "containers" in data


class TestHistoryAPI:
    """Test /api/history endpoint."""

    def test_history_returns_structure(self, app_client):
        r = app_client.get("/api/history")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "conversation" in data
        assert "logs" in data
        assert "current_step" in data
        assert isinstance(data["conversation"], list)
        assert isinstance(data["logs"], list)


class TestContainersAPI:
    """Test /api/containers endpoint."""

    def test_containers_returns_list(self, app_client):
        r = app_client.get("/api/containers")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)


class TestLogsTailAPI:
    """Test /api/logs/tail endpoint."""

    def test_logs_tail(self, app_client):
        r = app_client.get("/api/logs/tail")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "lines" in data
        assert "total" in data


class TestSyncAPI:
    """Test /api/tickets/sync endpoint."""

    def test_sync_no_integrations(self, app_client):
        r = app_client.post("/api/tickets/sync")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["ok"] is True
        assert data["results"] == {}


class TestProcessesAPI:
    """Test /api/processes endpoint."""

    def test_processes_returns_list(self, app_client):
        r = app_client.get("/api/processes")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, list)


class TestEnvAPI:
    """Test /api/env endpoint."""

    def test_env_returns_json(self, app_client):
        r = app_client.get("/api/env")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, dict)
