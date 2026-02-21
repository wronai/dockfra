"""
dockfra.db — SQLite event store (Event Sourcing persistence layer).

Single Responsibility: Only handles event persistence and retrieval.
Open/Closed: New event types need no schema changes.
Dependency Inversion: Pure functions, no framework dependencies.

Tables:
  events — append-only log of all system events (immutable)
"""
import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import Optional

_DB_PATH: Optional[Path] = None
_db_lock = threading.Lock()


def init_db(path) -> None:
    """Initialize SQLite database and create schema if needed."""
    global _DB_PATH
    _DB_PATH = Path(path)
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                ts    REAL    NOT NULL,
                src   TEXT    NOT NULL DEFAULT 'system',
                event TEXT    NOT NULL,
                data  TEXT    NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_id ON events(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event ON events(event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_src ON events(src)")
        conn.commit()


# ── Commands (write side) ────────────────────────────────────────────────────

def append_event(event: str, data: dict, src: str = "system") -> int:
    """Append a single immutable event. Returns event ID."""
    if not _DB_PATH:
        return 0
    try:
        with _db_lock:
            with _connect() as conn:
                cur = conn.execute(
                    "INSERT INTO events (ts, src, event, data) VALUES (?,?,?,?)",
                    (time.time(), src, event, json.dumps(data, ensure_ascii=False))
                )
                conn.commit()
                return cur.lastrowid or 0
    except Exception:
        return 0


def append_batch(events: list[tuple[str, dict, str]]) -> list[int]:
    """Append multiple events atomically. Each tuple: (event, data, src)."""
    if not _DB_PATH or not events:
        return []
    ids = []
    try:
        with _db_lock:
            with _connect() as conn:
                for event, data, src in events:
                    cur = conn.execute(
                        "INSERT INTO events (ts, src, event, data) VALUES (?,?,?,?)",
                        (time.time(), src, event, json.dumps(data, ensure_ascii=False))
                    )
                    ids.append(cur.lastrowid or 0)
                conn.commit()
    except Exception:
        return ids
    return ids


# ── Queries (read side) ─────────────────────────────────────────────────────

def get_events(since_id: int = 0, limit: int = 500,
               event_type: Optional[str] = None,
               src: Optional[str] = None) -> list:
    """Query events with optional filters. Never modifies state."""
    if not _DB_PATH:
        return []
    try:
        clauses = ["id > ?"]
        params: list = [since_id]
        if event_type:
            clauses.append("event = ?")
            params.append(event_type)
        if src:
            clauses.append("src = ?")
            params.append(src)
        params.append(limit)
        where = " AND ".join(clauses)
        with _connect() as conn:
            rows = conn.execute(
                f"SELECT id, ts, src, event, data FROM events WHERE {where} ORDER BY id LIMIT ?",
                params
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


def get_max_id() -> int:
    """Get the highest event ID (for polling cursors)."""
    if not _DB_PATH:
        return 0
    try:
        with _connect() as conn:
            row = conn.execute("SELECT MAX(id) FROM events").fetchone()
            return row[0] or 0
    except Exception:
        return 0


def count_events(event_type: Optional[str] = None, src: Optional[str] = None) -> int:
    """Count events with optional filters."""
    if not _DB_PATH:
        return 0
    try:
        clauses = ["1=1"]
        params: list = []
        if event_type:
            clauses.append("event = ?")
            params.append(event_type)
        if src:
            clauses.append("src = ?")
            params.append(src)
        where = " AND ".join(clauses)
        with _connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM events WHERE {where}", params).fetchone()
            return row[0] or 0
    except Exception:
        return 0


def get_latest_by_type(event_type: str, limit: int = 1) -> list:
    """Get the N most recent events of a given type."""
    if not _DB_PATH:
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT id, ts, src, event, data FROM events WHERE event = ? ORDER BY id DESC LIMIT ?",
                (event_type, limit)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


# ── Internal ─────────────────────────────────────────────────────────────────

def _row_to_dict(r: tuple) -> dict:
    """Convert a DB row tuple to event dict."""
    return {"id": r[0], "ts": r[1], "src": r[2], "event": r[3], "data": json.loads(r[4])}


def _connect() -> sqlite3.Connection:
    """Create a new SQLite connection (thread-safe via check_same_thread=False)."""
    return sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=5)
