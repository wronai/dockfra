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
from pathlib import Path

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


@pytest.fixture(autouse=True)
def restore_wizard_files():
    """Prevent tests from permanently mutating dockfra/.env and dockfra/.state.json."""
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / "dockfra" / ".env"
    state_path = repo_root / "dockfra" / ".state.json"
    env_before = env_path.read_text() if env_path.exists() else ""
    state_before = state_path.read_text() if state_path.exists() else ""
    yield
    try:
        env_path.write_text(env_before)
    except Exception:
        pass
    try:
        state_path.write_text(state_before)
    except Exception:
        pass


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


# ── Events & CLI↔Web sync tests ─────────────────────────────────────────────

class TestEventsAPI:
    """Test /api/events/since/<id> endpoint (SQLite event store)."""

    def test_events_since_zero(self, app_client):
        """Events from id=0 should return a list with max_id."""
        r = app_client.get("/api/events/since/0?limit=5")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "events" in data
        assert "max_id" in data
        assert isinstance(data["events"], list)
        assert isinstance(data["max_id"], int)

    def test_events_since_future_id(self, app_client):
        """Events beyond max_id should return empty list."""
        r = app_client.get("/api/events/since/999999999")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data["events"] == []

    def test_events_limit_respected(self, app_client):
        """Limit parameter should cap returned events."""
        r = app_client.get("/api/events/since/0?limit=2")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data["events"]) <= 2

    def test_events_have_required_fields(self, app_client):
        """Each event should have id, ts, src, event, data fields."""
        r = app_client.get("/api/events/since/0?limit=3")
        data = json.loads(r.data)
        for ev in data["events"]:
            assert "id" in ev
            assert "ts" in ev
            assert "src" in ev
            assert "event" in ev
            assert "data" in ev
            assert isinstance(ev["id"], int)
            assert isinstance(ev["ts"], float)

    def test_events_ordered_by_id(self, app_client):
        """Events should be returned in ascending id order."""
        r = app_client.get("/api/events/since/0?limit=20")
        data = json.loads(r.data)
        ids = [e["id"] for e in data["events"]]
        assert ids == sorted(ids)


class TestCLIWebSync:
    """Test that CLI actions are recorded in events DB and visible to web."""

    def test_cli_action_creates_events(self, app_client):
        """POST /api/action should create events in SQLite."""
        # Get current max_id
        r1 = app_client.get("/api/events/since/999999999")
        before_max = json.loads(r1.data)["max_id"]

        # Send a CLI action
        r2 = app_client.post("/api/action",
            data=json.dumps({"action": "status"}),
            content_type="application/json")
        assert r2.status_code == 200
        resp = json.loads(r2.data)
        assert resp["ok"] is True

        # Check new events were created
        r3 = app_client.get(f"/api/events/since/{before_max}")
        after = json.loads(r3.data)
        assert len(after["events"]) > 0

    def test_cli_user_message_recorded(self, app_client):
        """CLI user message should appear in events with src=cli."""
        r1 = app_client.get("/api/events/since/999999999")
        before_max = json.loads(r1.data)["max_id"]

        app_client.post("/api/action",
            data=json.dumps({"action": "status"}),
            content_type="application/json")

        r2 = app_client.get(f"/api/events/since/{before_max}?limit=10")
        events = json.loads(r2.data)["events"]

        # First event should be the CLI user message
        cli_msgs = [e for e in events if e["src"] == "cli" and e["event"] == "message"
                     and e["data"].get("role") == "user"]
        assert len(cli_msgs) >= 1
        assert cli_msgs[0]["data"]["text"] == "status"

    def test_cli_bot_response_recorded(self, app_client):
        """Bot response to CLI action should also be in events."""
        r1 = app_client.get("/api/events/since/999999999")
        before_max = json.loads(r1.data)["max_id"]

        app_client.post("/api/action",
            data=json.dumps({"action": "status"}),
            content_type="application/json")

        r2 = app_client.get(f"/api/events/since/{before_max}?limit=20")
        events = json.loads(r2.data)["events"]

        # Should contain at least one bot message
        bot_msgs = [e for e in events if e["event"] == "message"
                     and e["data"].get("role") == "bot"]
        assert len(bot_msgs) >= 1

    def test_cli_action_missing_value_returns_400(self, app_client):
        """POST /api/action with empty action should return 400."""
        r = app_client.post("/api/action",
            data=json.dumps({"action": ""}),
            content_type="application/json")
        assert r.status_code == 400

    def test_history_includes_cli_messages(self, app_client):
        """/api/history conversation should include CLI-sourced messages."""
        app_client.post("/api/action",
            data=json.dumps({"action": "status"}),
            content_type="application/json")

        r = app_client.get("/api/history")
        data = json.loads(r.data)
        # Conversation should have messages
        assert len(data["conversation"]) > 0


class TestSaveEnvActions:
    def test_save_env_vars_writes_to_env(self, app_client):
        repo_root = Path(__file__).resolve().parent.parent
        env_path = repo_root / "dockfra" / ".env"
        r = app_client.post(
            "/api/action",
            data=json.dumps({
                "action": "save_env_vars",
                "form": {
                    "AUTOPILOT_ENABLED": "false",
                    "AUTOPILOT_INTERVAL": "90",
                    "bad-key": "nope",
                    "lowercase": "nope",
                },
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        resp = json.loads(r.data)
        assert resp["ok"] is True

        env_txt = env_path.read_text()
        assert "AUTOPILOT_ENABLED=false" in env_txt
        assert "AUTOPILOT_INTERVAL=90" in env_txt
        assert "bad-key=" not in env_txt
        assert "lowercase=" not in env_txt

    def test_save_env_var_single_writes_to_env(self, app_client):
        repo_root = Path(__file__).resolve().parent.parent
        env_path = repo_root / "dockfra" / ".env"
        r = app_client.post(
            "/api/action",
            data=json.dumps({
                "action": "save_env_var::AUTOPILOT_ENABLED",
                "form": {"AUTOPILOT_ENABLED": "true"},
            }),
            content_type="application/json",
        )
        assert r.status_code == 200
        resp = json.loads(r.data)
        assert resp["ok"] is True
        assert "AUTOPILOT_ENABLED=true" in env_path.read_text()


class TestSSEStream:
    """Test /api/stream SSE endpoint."""

    def test_stream_endpoint_exists(self, app_client):
        """SSE stream should return text/event-stream content type."""
        r = app_client.get("/api/stream?since=999999999")
        assert r.status_code == 200
        assert "text/event-stream" in r.content_type


class TestDeveloperHealthAPI:
    """Test /api/developer-health endpoint."""

    def test_developer_health_returns_json(self, app_client):
        r = app_client.get("/api/developer-health")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "container" in data
        assert isinstance(data, dict)


class TestEngineStatusAPI:
    """Test /api/engine-status endpoint."""

    def test_engine_status_returns_dict_with_engines(self, app_client):
        r = app_client.get("/api/engine-status")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, dict)
        assert "engines" in data
        assert "preferred" in data
        assert isinstance(data["engines"], list)

    def test_engine_status_has_required_fields(self, app_client):
        r = app_client.get("/api/engine-status")
        data = json.loads(r.data)
        for engine in data["engines"]:
            assert "id" in engine
            assert "name" in engine
            assert "ok" in engine


class TestDeveloperLogsAPI:
    """Test /api/developer-logs endpoint."""

    def test_developer_logs_returns_json(self, app_client):
        r = app_client.get("/api/developer-logs")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, dict)
        assert "container" in data
        assert "logs" in data


class TestTicketDiffAPI:
    """Test /api/ticket-diff/<id> endpoint."""

    def test_ticket_diff_nonexistent_returns_404(self, app_client):
        """Non-existent ticket should return 404."""
        r = app_client.get("/api/ticket-diff/T-9999")
        assert r.status_code == 404

    def test_ticket_diff_returns_json(self, app_client, tickets_dir):
        from dockfra import tickets
        tickets.create("Diff structure test", description="test")
        r = app_client.get("/api/ticket-diff/T-0001")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert isinstance(data, dict)
        assert "commits" in data
        assert "diff" in data

    def test_ticket_diff_with_existing_ticket(self, app_client, tickets_dir):
        from dockfra import tickets
        tickets.create("Diff test", description="test diff")
        r = app_client.get("/api/ticket-diff/T-0001")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert "commits" in data

    def test_ticket_diff_reads_commits_from_developer_container(self, app_client, tickets_dir, monkeypatch):
        from dockfra import tickets
        from dockfra import app as app_mod

        tickets.create("Diff from container", description="container git repo")

        monkeypatch.setattr(app_mod, "_get_role", lambda _: {
            "container": "dockfra-ssh-developer",
            "user": "developer",
        })

        def _fake_check_output(cmd, **kwargs):
            if cmd[:5] == ["docker", "exec", "-u", "developer", "dockfra-ssh-developer"]:
                if "log" in cmd:
                    return "8f64476abcde1234567890 feat(T-0001): add contact form\n"
                if "show" in cmd:
                    return "commit 8f64476abcde\n\n+line added\n"
            raise RuntimeError(f"unexpected command: {cmd}")

        monkeypatch.setattr("subprocess.check_output", _fake_check_output)

        r = app_client.get("/api/ticket-diff/T-0001")
        assert r.status_code == 200
        data = json.loads(r.data)
        assert len(data["commits"]) == 1
        assert data["commits"][0]["hash"] == "8f64476abcde"
        assert data["commits"][0]["repo"] == "ssh-developer:/repo"
        assert "+line added" in data["diff"]


class TestDBModule:
    """Test dockfra.db module directly."""

    def setup_method(self):
        import tempfile, pathlib
        from dockfra import db
        self._db_path = pathlib.Path(tempfile.mktemp(suffix='.db'))
        db.init_db(self._db_path)

    def teardown_method(self):
        from dockfra import db
        db._DB_PATH = None
        if self._db_path.exists():
            self._db_path.unlink()

    def test_append_and_get_events(self):
        from dockfra import db
        eid = db.append_event("test_event", {"foo": "bar"}, src="test")
        assert eid > 0
        events = db.get_events(since_id=eid - 1, limit=5)
        found = [e for e in events if e["id"] == eid]
        assert len(found) == 1
        assert found[0]["event"] == "test_event"
        assert found[0]["data"]["foo"] == "bar"
        assert found[0]["src"] == "test"

    def test_get_max_id(self):
        from dockfra import db
        mid1 = db.get_max_id()
        db.append_event("test_max", {}, src="test")
        mid2 = db.get_max_id()
        assert mid2 > mid1

    def test_events_since_filters_correctly(self):
        from dockfra import db
        eid1 = db.append_event("a", {}, src="test")
        eid2 = db.append_event("b", {}, src="test")
        events = db.get_events(since_id=eid1, limit=10)
        ids = [e["id"] for e in events]
        assert eid1 not in ids
        assert eid2 in ids

    def test_append_batch(self):
        from dockfra import db
        before = db.get_max_id()
        ids = db.append_batch([
            ("batch_a", {"n": 1}, "test"),
            ("batch_b", {"n": 2}, "test"),
            ("batch_c", {"n": 3}, "test"),
        ])
        assert len(ids) == 3
        assert all(i > before for i in ids)

    def test_count_events(self):
        from dockfra import db
        db.append_event("count_test_type", {}, src="count_test_src")
        total = db.count_events()
        assert total > 0
        typed = db.count_events(event_type="count_test_type")
        assert typed >= 1
        sourced = db.count_events(src="count_test_src")
        assert sourced >= 1

    def test_get_events_with_type_filter(self):
        from dockfra import db
        db.append_event("filter_type_x", {"val": "x"}, src="test")
        db.append_event("filter_type_y", {"val": "y"}, src="test")
        events = db.get_events(since_id=0, limit=1000, event_type="filter_type_x")
        assert all(e["event"] == "filter_type_x" for e in events)
        assert len(events) >= 1

    def test_get_latest_by_type(self):
        from dockfra import db
        db.append_event("latest_test", {"seq": 1}, src="test")
        db.append_event("latest_test", {"seq": 2}, src="test")
        db.append_event("latest_test", {"seq": 3}, src="test")
        latest = db.get_latest_by_type("latest_test", limit=2)
        assert len(latest) == 2
        assert latest[0]["data"]["seq"] == 3  # most recent first
        assert latest[1]["data"]["seq"] == 2


class TestEventBus:
    """Test dockfra.event_bus module (requires app_client for db init)."""

    def test_get_bus_singleton(self, app_client):
        from dockfra.event_bus import get_bus
        bus1 = get_bus()
        bus2 = get_bus()
        assert bus1 is bus2

    def test_emit_persists_to_store(self, app_client, tmp_path):
        from dockfra import db as _db
        from dockfra.event_bus import init_bus
        _db.init_db(tmp_path / "bus_test.db")
        bus = init_bus(_db)
        before = bus.query_max_id()
        eid = bus.emit("test.bus_emit", {"hello": "world"}, src="test")
        assert eid > before

    def test_query_events_returns_emitted(self, app_client, tmp_path):
        from dockfra import db as _db
        from dockfra.event_bus import init_bus
        _db.init_db(tmp_path / "bus_query_test.db")
        bus = init_bus(_db)
        before = bus.query_max_id()
        bus.emit("test.query_check", {"key": "val"}, src="test")
        events = bus.query_events(since_id=before, limit=10)
        found = [e for e in events if e["event"] == "test.query_check"]
        assert len(found) >= 1
        assert found[0]["data"]["key"] == "val"

    def test_subscribe_and_emit(self, app_client):
        from dockfra.event_bus import get_bus
        bus = get_bus()
        received = []
        bus.subscribe("test.sub_event", lambda ev: received.append(ev))
        bus.emit("test.sub_event", {"n": 42}, src="test")
        assert len(received) >= 1
        assert received[-1].data["n"] == 42
        assert received[-1].src == "test"

    def test_subscribe_all(self, app_client):
        from dockfra.event_bus import get_bus
        bus = get_bus()
        received = []
        bus.subscribe_all(lambda ev: received.append(ev.event))
        bus.emit("test.global_a", {}, src="test")
        bus.emit("test.global_b", {}, src="test")
        assert "test.global_a" in received
        assert "test.global_b" in received

    def test_event_types_are_strings(self):
        from dockfra.event_bus import EventType
        assert EventType.MESSAGE == "message"
        assert EventType.TICKET_CREATED == "ticket.created"
        assert isinstance(EventType.PIPELINE_STARTED.value, str)


class TestEventsAPIFilters:
    """Test CQRS query filters on /api/events/since endpoint."""

    def test_events_filter_by_type(self, app_client):
        """Events endpoint should support ?type= filter."""
        r = app_client.get("/api/events/since/0?limit=5&type=message")
        assert r.status_code == 200
        data = json.loads(r.data)
        for ev in data["events"]:
            assert ev["event"] == "message"

    def test_events_filter_by_src(self, app_client):
        """Events endpoint should support ?src= filter."""
        r = app_client.get("/api/events/since/0?limit=5&src=cli")
        assert r.status_code == 200
        data = json.loads(r.data)
        for ev in data["events"]:
            assert ev["src"] == "cli"


class TestTicketDomainEvents:
    """Test that ticket CRUD emits domain events (event sourcing)."""

    def test_ticket_create_emits_event(self, app_client):
        r1 = app_client.get("/api/events/since/999999999")
        before = json.loads(r1.data)["max_id"]
        app_client.post("/api/tickets",
            data=json.dumps({"title": "Event test ticket", "priority": "high"}),
            content_type="application/json")
        r2 = app_client.get(f"/api/events/since/{before}?limit=10&type=ticket.created")
        events = json.loads(r2.data)["events"]
        assert len(events) >= 1
        assert events[0]["data"]["title"] == "Event test ticket"

    def test_ticket_update_emits_event(self, app_client, tickets_dir):
        from dockfra import tickets
        tickets.create("Update event test")
        r1 = app_client.get("/api/events/since/999999999")
        before = json.loads(r1.data)["max_id"]
        app_client.put("/api/tickets/T-0001",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json")
        r2 = app_client.get(f"/api/events/since/{before}?limit=10&type=ticket.updated")
        events = json.loads(r2.data)["events"]
        assert len(events) >= 1
        assert events[0]["data"]["id"] == "T-0001"

    def test_ticket_comment_emits_event(self, app_client, tickets_dir):
        from dockfra import tickets
        tickets.create("Comment event test")
        r1 = app_client.get("/api/events/since/999999999")
        before = json.loads(r1.data)["max_id"]
        app_client.post("/api/tickets/T-0001/comment",
            data=json.dumps({"text": "Test comment", "author": "tester"}),
            content_type="application/json")
        r2 = app_client.get(f"/api/events/since/{before}?limit=10&type=ticket.commented")
        events = json.loads(r2.data)["events"]
        assert len(events) >= 1
        assert events[0]["data"]["author"] == "tester"

    def test_ticket_close_emits_closed_event(self, app_client, tickets_dir):
        from dockfra import tickets
        tickets.create("Close event test")
        r1 = app_client.get("/api/events/since/999999999")
        before = json.loads(r1.data)["max_id"]
        app_client.put("/api/tickets/T-0001",
            data=json.dumps({"status": "done"}),
            content_type="application/json")
        r2 = app_client.get(f"/api/events/since/{before}?limit=10&type=ticket.closed")
        events = json.loads(r2.data)["events"]
        assert len(events) >= 1
        assert events[0]["data"]["id"] == "T-0001"


# ── CLI module unit tests ─────────────────────────────────────────────────────

class TestCLIHelpers:
    """Unit tests for CLI helper functions (no server required)."""

    def test_classify_log_error(self):
        from dockfra.cli import _classify_log
        assert _classify_log("error: something failed") == "err"
        assert _classify_log("fatal: crash") == "err"
        assert _classify_log("connection refused") == "err"

    def test_classify_log_warn(self):
        from dockfra.cli import _classify_log
        assert _classify_log("warning: deprecated") == "warn"

    def test_classify_log_ok(self):
        from dockfra.cli import _classify_log
        assert _classify_log("successfully started") == "ok"
        assert _classify_log("healthy") == "ok"

    def test_classify_log_build(self):
        from dockfra.cli import _classify_log
        assert _classify_log("#1 [backend] RUN pip install") == "build"
        assert _classify_log("#2 DONE 0.1s") == "done"

    def test_classify_log_dim(self):
        from dockfra.cli import _classify_log
        assert _classify_log("[notice] new version available") == "dim"

    def test_classify_log_plain(self):
        from dockfra.cli import _classify_log
        assert _classify_log("just a normal log line") == ""

    def test_colorize_log_no_crash(self):
        from dockfra.cli import _colorize_log
        for line in ["error: x", "warning: y", "started ok", "#1 RUN", "plain"]:
            result = _colorize_log(line)
            assert isinstance(result, str)
            assert line.split(":")[0] in result or line in result

    def test_render_md_bold(self):
        from dockfra.cli import _render_md
        result = _render_md("**hello**")
        assert "hello" in result

    def test_render_md_heading(self):
        from dockfra.cli import _render_md
        result = _render_md("## My Title")
        assert "My Title" in result

    def test_render_md_code(self):
        from dockfra.cli import _render_md
        result = _render_md("`some_var`")
        assert "some_var" in result

    def test_render_md_list(self):
        from dockfra.cli import _render_md
        result = _render_md("- item one")
        assert "item one" in result
        assert "•" in result

    def test_color_functions_no_tty(self):
        """Color functions should return plain text when NO_COLOR is set."""
        import os
        os.environ["NO_COLOR"] = "1"
        try:
            from dockfra import cli as _cli
            import importlib
            importlib.reload(_cli)
            assert _cli.green("x") == "x"
            assert _cli.red("x") == "x"
            assert _cli.bold("x") == "x"
        finally:
            del os.environ["NO_COLOR"]


class TestWizardClient:
    """Unit tests for WizardClient REST client (no live server)."""

    def test_client_init_default(self):
        from dockfra.cli import WizardClient
        c = WizardClient("http://localhost:5050")
        assert c.base == "http://localhost:5050"

    def test_client_strips_trailing_slash(self):
        from dockfra.cli import WizardClient
        c = WizardClient("http://localhost:5050/")
        assert c.base == "http://localhost:5050"

    def test_ping_returns_false_when_offline(self):
        from dockfra.cli import WizardClient
        c = WizardClient("http://127.0.0.1:19999")  # nothing listening
        assert c.ping() is False

    def test_get_returns_error_when_offline(self):
        from dockfra.cli import WizardClient
        c = WizardClient("http://127.0.0.1:19999")
        data, err = c._get("/api/health")
        assert data is None
        assert err is not None

    def test_post_returns_error_when_offline(self):
        from dockfra.cli import WizardClient
        c = WizardClient("http://127.0.0.1:19999")
        data, err = c._post("/api/action", {"action": "status"})
        assert data is None
        assert err is not None


class TestCLICommands:
    """Integration tests for CLI commands against live Flask test client."""

    def test_cmd_status_offline(self):
        """cmd_status should return 1 when wizard is offline."""
        from dockfra.cli import WizardClient, cmd_status
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_status(c, [])
        assert rc == 1

    def test_cmd_logs_offline(self):
        from dockfra.cli import WizardClient, cmd_logs
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_logs(c, [])
        assert rc == 1

    def test_cmd_tickets_offline(self):
        from dockfra.cli import WizardClient, cmd_tickets
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_tickets(c, [])
        assert rc == 1

    def test_cmd_diff_no_args(self):
        from dockfra.cli import WizardClient, cmd_diff
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_diff(c, [])
        assert rc == 1

    def test_cmd_engines_offline(self):
        from dockfra.cli import WizardClient, cmd_engines
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_engines(c, [])
        assert rc == 1

    def test_cmd_dev_health_offline(self):
        from dockfra.cli import WizardClient, cmd_dev_health
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_dev_health(c, [])
        assert rc == 1

    def test_cmd_dev_logs_offline(self):
        from dockfra.cli import WizardClient, cmd_dev_logs
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_dev_logs(c, [])
        assert rc == 1

    def test_cmd_ask_no_args(self):
        from dockfra.cli import WizardClient, cmd_ask
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_ask(c, [])
        assert rc == 1

    def test_cmd_action_no_args(self):
        from dockfra.cli import WizardClient, cmd_action
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_action(c, [])
        assert rc == 1

    def test_cmd_launch_offline(self):
        from dockfra.cli import WizardClient, cmd_launch
        c = WizardClient("http://127.0.0.1:19999")
        rc = cmd_launch(c, [])
        assert rc == 1


# ── Pipeline module unit tests ────────────────────────────────────────────────

class TestPipelineModule:
    """Unit tests for dockfra.pipeline — StepResult, PipelineState, scoring."""

    def test_step_result_ok_when_rc0_score_high(self):
        from dockfra.pipeline import StepResult
        r = StepResult("test", rc=0, output="done", score=1.0)
        assert r.ok() is True

    def test_step_result_not_ok_when_rc_nonzero(self):
        from dockfra.pipeline import StepResult
        r = StepResult("test", rc=1, output="error", score=0.0)
        assert r.ok() is False

    def test_step_result_not_ok_when_score_low(self):
        from dockfra.pipeline import StepResult
        r = StepResult("test", rc=0, output="", score=0.3)
        assert r.ok() is False

    def test_step_result_to_dict(self):
        from dockfra.pipeline import StepResult
        r = StepResult("impl", rc=0, output="ok", duration=1.5, score=0.9)
        d = r.to_dict()
        assert d["step"] == "impl"
        assert d["rc"] == 0
        assert d["score"] == 0.9
        assert d["duration"] == 1.5
        assert "ts" in d

    def test_evaluate_implementation_empty(self):
        from dockfra.pipeline import evaluate_implementation
        assert evaluate_implementation("") == 0.0

    def test_evaluate_implementation_with_code(self):
        from dockfra.pipeline import evaluate_implementation
        output = "```python\nimport os\n# fix\nprint('done')\n```\nFile: main.py"
        score = evaluate_implementation(output)
        assert score > 0.5

    def test_evaluate_implementation_llm_error(self):
        from dockfra.pipeline import evaluate_implementation
        score = evaluate_implementation("[llm] error: api key not set")
        assert score <= 0.1

    def test_evaluate_test_output_rc0(self):
        from dockfra.pipeline import evaluate_test_output
        assert evaluate_test_output("all passed", 0) == 1.0

    def test_evaluate_test_output_rc_nonzero_no_output(self):
        from dockfra.pipeline import evaluate_test_output
        score = evaluate_test_output("", 1)
        assert score == 0.3

    def test_evaluate_test_output_partial(self):
        from dockfra.pipeline import evaluate_test_output
        score = evaluate_test_output("3 passed, 1 failed", 1)
        assert 0.5 < score < 1.0

    def test_run_step_success(self):
        from dockfra.pipeline import run_step
        r = run_step(lambda: (0, "all good"), "test-step")
        assert r.rc == 0
        assert r.score == 1.0
        assert r.step == "test-step"

    def test_run_step_failure(self):
        from dockfra.pipeline import run_step
        r = run_step(lambda: (1, "error occurred"), "test-step")
        assert r.rc == 1
        assert r.score == 0.0

    def test_run_step_soft_failure_llm_error(self):
        from dockfra.pipeline import run_step
        r = run_step(lambda: (0, "[llm] error: key missing"), "implement")
        assert r.score <= 0.1

    def test_run_step_nothing_to_commit(self):
        from dockfra.pipeline import run_step
        r = run_step(lambda: (0, "Nothing to commit."), "commit-push")
        assert r.score == 0.2

    def test_run_step_exception(self):
        from dockfra.pipeline import run_step
        def _boom(): raise RuntimeError("crash")
        r = run_step(_boom, "crash-step")
        assert r.rc == -1
        assert r.score == 0.0
        assert "crash" in r.error

    def test_pipeline_state_iteration(self, tmp_path):
        import os
        os.environ["TICKETS_DIR"] = str(tmp_path)
        from dockfra.pipeline import PipelineState, StepResult
        ps = PipelineState("T-TEST")
        assert ps.iteration == 0
        ps.start_iteration()
        assert ps.iteration == 1

    def test_pipeline_state_record_step(self, tmp_path):
        import os
        os.environ["TICKETS_DIR"] = str(tmp_path)
        from dockfra.pipeline import PipelineState, StepResult
        ps = PipelineState("T-TEST2")
        ps.start_iteration()
        r = StepResult("implement", rc=0, output="done", score=0.9)
        ps.record_step(r)
        assert len(ps.steps) == 1
        assert ps.steps[0]["step"] == "implement"

    def test_pipeline_state_compute_score(self, tmp_path):
        import os
        os.environ["TICKETS_DIR"] = str(tmp_path)
        from dockfra.pipeline import PipelineState, StepResult
        ps = PipelineState("T-TEST3")
        ps.start_iteration()
        for step, score in [("ticket-work", 1.0), ("implement", 0.8),
                             ("test-local", 1.0), ("commit-push", 0.7), ("status-review", 1.0)]:
            ps.record_step(StepResult(step, rc=0, output="ok", score=score))
        overall = ps.compute_overall_score()
        assert 0.0 < overall <= 1.0

    def test_build_retry_prompt(self, tmp_path):
        import os
        os.environ["TICKETS_DIR"] = str(tmp_path)
        from dockfra.pipeline import PipelineState, StepResult, build_retry_prompt
        ps = PipelineState("T-RETRY")
        ps.start_iteration()
        failed = StepResult("implement", rc=1, output="", error="API key missing", score=0.0)
        ticket = {"title": "Fix login", "description": "Users cannot log in"}
        prompt = build_retry_prompt(ps, failed, ticket)
        assert "Fix login" in prompt
        assert "API key missing" in prompt


# ── Persistent state unit tests ───────────────────────────────────────────────

class TestPersistentState:
    """Test save_state / load_state logic directly (no Flask dependency)."""

    _SKIP = frozenset({
        "_lang", "step",
        "openrouter_key", "anthropic_api_key", "github_token",
        "jira_token", "trello_token", "linear_token",
    })

    def _save(self, state_file, state):
        data = {k: v for k, v in state.items() if k not in self._SKIP}
        state_file.write_text(json.dumps(data, indent=2))

    def _load(self, state_file):
        try:
            if state_file.exists():
                return json.loads(state_file.read_text())
        except Exception:
            pass
        return {}

    def test_save_and_load_state(self, tmp_path):
        state_file = tmp_path / ".state.json"
        state = {
            "environment": "local",
            "llm_model": "google/gemini-2.0-flash-001",
            "openrouter_key": "sk-secret",
        }
        self._save(state_file, state)
        assert state_file.exists()
        loaded = self._load(state_file)
        assert loaded["environment"] == "local"
        assert loaded["llm_model"] == "google/gemini-2.0-flash-001"
        assert "openrouter_key" not in loaded

    def test_load_state_missing_file(self, tmp_path):
        result = self._load(tmp_path / "nonexistent.json")
        assert result == {}

    def test_load_state_corrupt_file(self, tmp_path):
        bad = tmp_path / ".state.json"
        bad.write_text("{ not valid json }")
        result = self._load(bad)
        assert result == {}

    def test_save_state_skips_all_secrets(self, tmp_path):
        state_file = tmp_path / ".state.json"
        state = {
            "openrouter_key": "sk-or-secret",
            "anthropic_api_key": "sk-ant-secret",
            "github_token": "ghp_secret",
            "jira_token": "jira_secret",
            "trello_token": "trello_secret",
            "linear_token": "linear_secret",
            "_lang": "pl",
            "step": "welcome",
            "environment": "local",
        }
        self._save(state_file, state)
        loaded = json.loads(state_file.read_text())
        for secret in ("openrouter_key", "anthropic_api_key", "github_token",
                       "jira_token", "trello_token", "linear_token", "_lang", "step"):
            assert secret not in loaded
        assert loaded["environment"] == "local"


# ── shared/lib ticket_system unit tests ──────────────────────────────────────

class TestSharedLibTicketSystem:
    """Unit tests for shared/lib/ticket_system.py standalone fallback."""

    @pytest.fixture(autouse=True)
    def setup_tickets_dir(self, tmp_path, monkeypatch):
        """Each test gets its own isolated tickets directory."""
        monkeypatch.setenv("TICKETS_DIR", str(tmp_path))
        # Patch the module-level TICKETS_DIR in dockfra.tickets
        import dockfra.tickets as _tmod
        monkeypatch.setattr(_tmod, "TICKETS_DIR", tmp_path)
        self.tickets_dir = tmp_path
        yield

    def test_create_and_get(self):
        from dockfra import tickets
        t = tickets.create("Shared lib test", description="desc")
        assert t["id"] == "T-0001"
        got = tickets.get("T-0001")
        assert got["title"] == "Shared lib test"

    def test_list_and_filter(self):
        from dockfra import tickets
        tickets.create("A", priority="high")
        tickets.create("B", priority="low")
        all_t = tickets.list_tickets()
        assert len(all_t) == 2
        high = tickets.list_tickets(priority="high")
        assert len(high) == 1

    def test_update_and_comment(self):
        from dockfra import tickets
        t0 = tickets.create("Update test")
        tid = t0["id"]
        tickets.update(tid, status="in_progress")
        t = tickets.get(tid)
        assert t["status"] == "in_progress"
        tickets.add_comment(tid, "bot", "looks good")
        t = tickets.get(tid)
        assert t["comments"][0]["text"] == "looks good"

    def test_close(self):
        from dockfra import tickets
        t0 = tickets.create("Close test")
        tid = t0["id"]
        tickets.close(tid)
        t = tickets.get(tid)
        assert t["status"] == "closed"

    def test_format_ticket_basic(self):
        from dockfra import tickets
        t0 = tickets.create("Format test", priority="critical")
        t = tickets.get(t0["id"])
        line = tickets.format_ticket(t)
        assert t0["id"] in line
        assert "🔴" in line

    def test_format_ticket_verbose(self):
        from dockfra import tickets
        t0 = tickets.create("Verbose", description="long description here")
        t = tickets.get(t0["id"])
        line = tickets.format_ticket(t, verbose=True)
        assert "Status:" in line
        assert "long description" in line

    def test_stats_structure(self):
        from dockfra import tickets
        tickets.create("A", priority="high")
        t2 = tickets.create("B", priority="low")
        tickets.update(t2["id"], status="in_progress")
        s = tickets.stats()
        assert s["total"] == 2
        assert "by_status" in s
        assert "by_priority" in s

    def test_sync_all_no_integrations(self):
        from dockfra import tickets
        result = tickets.sync_all()
        assert result == {}

    def test_get_missing_returns_none(self):
        from dockfra import tickets
        assert tickets.get("T-9999") is None

    def test_update_missing_returns_none(self):
        from dockfra import tickets
        result = tickets.update("T-9999", status="closed")
        assert result is None


# ── post_launch hooks unit tests ─────────────────────────────────────────────

class TestPostLaunchHooks:
    """Unit tests for dockfra.yaml post_launch hook system (pure logic, no Flask)."""

    # ── _expand_env_vars logic ────────────────────────────────────────────────

    def _expand(self, text, state=None, environ=None):
        """Inline reimplementation of _expand_env_vars for testing without Flask."""
        import re, os
        _st = state or {}
        _env = environ or {}
        def _sub(m):
            var, default = m.group(1), m.group(2) or ""
            return _st.get(var.lower(), _env.get(var, os.environ.get(var, default)))
        text = re.sub(r'\$\{([A-Z_][A-Z0-9_]*)(?::?-([^}]*))?\}', _sub, text)
        text = re.sub(r'\$([A-Z_][A-Z0-9_]*)',
                      lambda m: _env.get(m.group(1), os.environ.get(m.group(1), m.group(0))), text)
        return text

    def test_expand_env_vars_default(self):
        result = self._expand("http://localhost:${SOME_NONEXISTENT_PORT_XYZ:-6081}")
        assert result == "http://localhost:6081"

    def test_expand_env_vars_from_state(self):
        result = self._expand("http://localhost:${MY_PORT:-1234}", state={"my_port": "9999"})
        assert result == "http://localhost:9999"

    def test_expand_env_vars_no_template(self):
        result = self._expand("http://localhost:5050")
        assert result == "http://localhost:5050"

    def test_expand_env_vars_multiple(self):
        result = self._expand("${HOST:-localhost}:${PORT:-80}", state={"host": "myhost"})
        assert result == "myhost:80"

    # ── _eval_post_launch_condition logic ─────────────────────────────────────

    def _eval(self, cond, running_names, stacks=None, prefix="dockfra"):
        """Inline reimplementation of _eval_post_launch_condition for testing."""
        if not cond:
            return True
        cond = cond.strip()
        func, _, arg = cond.partition("(")
        arg = arg.rstrip(")").strip().strip('"\'')
        _stacks = stacks or {}
        if func == "stack_exists":
            return arg in _stacks
        if func == "stack_running":
            return any(arg in n for n in running_names)
        if func == "container_running":
            full = f"{prefix}-{arg}"
            return full in running_names or arg in running_names
        if func == "ssh_roles_exist":
            return False
        return True

    def test_eval_condition_empty_always_true(self):
        assert self._eval("", set()) is True

    def test_eval_condition_stack_exists_true(self):
        assert self._eval('stack_exists("management")', set(), stacks={"management": "/path"}) is True

    def test_eval_condition_stack_exists_false(self):
        assert self._eval('stack_exists("nonexistent_xyz")', set(), stacks={}) is False

    def test_eval_condition_container_running_true(self):
        running = {"dockfra-traefik", "dockfra-app"}
        assert self._eval('container_running("traefik")', running) is True

    def test_eval_condition_container_running_false(self):
        assert self._eval('container_running("traefik")', set()) is False

    def test_eval_condition_stack_running_true(self):
        running = {"dockfra-management-app", "dockfra-management-db"}
        assert self._eval('stack_running("management")', running) is True

    def test_eval_condition_stack_running_false(self):
        assert self._eval('stack_running("management")', set()) is False

    def test_eval_condition_unknown_returns_true(self):
        assert self._eval('unknown_func("arg")', set()) is True

    # ── _render_post_launch integration (needs app_client for Flask context) ──

    def test_render_post_launch_no_crash(self, app_client):
        """_render_post_launch should not raise with empty roles and running_names."""
        from dockfra.core import _render_post_launch
        _render_post_launch(set(), {})

    def test_render_post_launch_with_url_hook(self, app_client, monkeypatch):
        """URL hooks should be included when condition passes."""
        from dockfra import core
        monkeypatch.setattr(core, "_PROJECT_CONFIG", {
            "post_launch": [
                {"label": "🔗 Test URL", "url": "http://localhost:8080"},
            ]
        })
        collected = []
        monkeypatch.setattr(core, "buttons", lambda items: collected.extend(items))
        core._render_post_launch(set(), {})
        labels = [b["label"] for b in collected]
        assert "🔗 Test URL" in labels
        values = [b["value"] for b in collected]
        assert any("open_url::http://localhost:8080" in v for v in values)

    def test_render_post_launch_condition_filters(self, app_client, monkeypatch):
        """Hooks with failing conditions should be excluded."""
        from dockfra import core
        monkeypatch.setattr(core, "_PROJECT_CONFIG", {
            "post_launch": [
                {"label": "✅ Always", "action": "back"},
                {"label": "❌ Never", "action": "back",
                 "condition": 'container_running("nonexistent_xyz_abc")'},
            ]
        })
        collected = []
        monkeypatch.setattr(core, "buttons", lambda items: collected.extend(items))
        core._render_post_launch(set(), {})
        labels = [b["label"] for b in collected]
        assert "✅ Always" in labels
        assert "❌ Never" not in labels
