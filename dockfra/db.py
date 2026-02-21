"""SQLite persistence for Dockfra events — shared between CLI and web."""
import sqlite3, json, time, threading
from pathlib import Path

_DB_PATH: "Path | None" = None
_db_lock = threading.Lock()


def init_db(path) -> None:
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
        conn.commit()


def append_event(event: str, data: dict, src: str = 'system') -> int:
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


def get_events(since_id: int = 0, limit: int = 500) -> list:
    if not _DB_PATH:
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT id, ts, src, event, data FROM events WHERE id > ? ORDER BY id LIMIT ?",
                (since_id, limit)
            ).fetchall()
        return [
            {"id": r[0], "ts": r[1], "src": r[2], "event": r[3], "data": json.loads(r[4])}
            for r in rows
        ]
    except Exception:
        return []


def get_max_id() -> int:
    if not _DB_PATH:
        return 0
    try:
        with _connect() as conn:
            row = conn.execute("SELECT MAX(id) FROM events").fetchone()
            return row[0] or 0
    except Exception:
        return 0


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=5)
