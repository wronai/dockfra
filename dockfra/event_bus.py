"""
dockfra.event_bus — Event Sourcing bus with CQRS separation.

Principles:
  - Single Responsibility: Each event type has one purpose
  - Open/Closed: New event types added without modifying existing code
  - Dependency Inversion: Handlers depend on EventBus interface, not concrete DB
  - Event Sourcing: All state changes recorded as immutable events
  - CQRS: Commands produce events, Queries read projections

Usage:
    bus = get_bus()
    bus.subscribe("ticket.created", my_handler)
    bus.emit("ticket.created", {"id": "T-0001", "title": "Fix bug"}, src="manager")
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)

# ── Event Types (Open/Closed — extend by adding members, never modify) ───────

class EventType(str, Enum):
    # System lifecycle
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"

    # Chat / UI messages
    MESSAGE = "message"
    WIDGET = "widget"
    CLEAR_WIDGETS = "clear_widgets"
    LOG_LINE = "log_line"

    # Ticket domain (commands produce these)
    TICKET_CREATED = "ticket.created"
    TICKET_UPDATED = "ticket.updated"
    TICKET_CLOSED = "ticket.closed"
    TICKET_COMMENTED = "ticket.commented"
    TICKET_ASSIGNED = "ticket.assigned"

    # Pipeline domain
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_STEP_DONE = "pipeline.step_done"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"

    # Engine domain
    ENGINE_DETECTED = "engine.detected"
    ENGINE_SELECTED = "engine.selected"
    ENGINE_TEST_RESULT = "engine.test_result"

    # Config error domain
    CONFIG_ERROR = "config.error"
    CONFIG_FIXED = "config.fixed"

    # Container domain
    CONTAINER_STARTED = "container.started"
    CONTAINER_STOPPED = "container.stopped"
    CONTAINER_HEALTH = "container.health"

    # Deploy domain
    DEPLOY_STARTED = "deploy.started"
    DEPLOY_COMPLETED = "deploy.completed"
    DEPLOY_FAILED = "deploy.failed"


# ── Event dataclass (immutable value object) ─────────────────────────────────

@dataclass(frozen=True)
class Event:
    """Immutable event — the atom of event sourcing."""
    event: str
    data: dict
    src: str = "system"
    ts: float = field(default_factory=time.time)
    id: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ── Event Store Protocol (Dependency Inversion — depend on abstraction) ──────

class EventStore(Protocol):
    """Interface for event persistence — any backend can implement this."""
    def append(self, event: str, data: dict, src: str) -> int: ...
    def get_since(self, since_id: int, limit: int) -> list[dict]: ...
    def get_max_id(self) -> int: ...


# ── SQLite Event Store (concrete implementation) ─────────────────────────────

class SQLiteEventStore:
    """Adapts dockfra.db module to EventStore protocol."""

    def __init__(self, db_module):
        self._db = db_module

    def append(self, event: str, data: dict, src: str = "system") -> int:
        return self._db.append_event(event, data, src=src)

    def get_since(self, since_id: int = 0, limit: int = 500) -> list[dict]:
        return self._db.get_events(since_id=since_id, limit=limit)

    def get_max_id(self) -> int:
        return self._db.get_max_id()


# ── Event Bus (mediator + observer pattern) ──────────────────────────────────

EventHandler = Callable[[Event], None]


class EventBus:
    """
    Central event bus — CQRS command side.

    Commands emit events → events persisted to store → handlers notified.
    Queries read from store directly (no bus involvement).
    """

    def __init__(self, store: EventStore | None = None):
        self._store = store
        self._handlers: dict[str, list[EventHandler]] = {}
        self._global_handlers: list[EventHandler] = []
        self._lock = threading.Lock()

    def set_store(self, store: EventStore) -> None:
        """Late-bind store (for startup ordering)."""
        self._store = store

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to specific event type."""
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events (for projections, logging)."""
        with self._lock:
            self._global_handlers.append(handler)

    def emit(self, event_type: str, data: dict, src: str = "system") -> int:
        """
        Command side: emit event → persist → notify handlers.
        Returns event ID from store (0 if no store).
        """
        event_id = 0
        if self._store:
            event_id = self._store.append(event_type, data, src)

        ev = Event(event=event_type, data=data, src=src, id=event_id)

        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
            global_h = list(self._global_handlers)

        for h in handlers + global_h:
            try:
                h(ev)
            except Exception:
                logger.exception("Event handler error for %s", event_type)

        return event_id

    def query_events(self, since_id: int = 0, limit: int = 500) -> list[dict]:
        """Query side: read events from store."""
        if not self._store:
            return []
        return self._store.get_since(since_id, limit)

    def query_max_id(self) -> int:
        """Query side: get latest event ID."""
        if not self._store:
            return 0
        return self._store.get_max_id()

    def replay(self, since_id: int = 0, handler: EventHandler | None = None) -> int:
        """Replay events from store through a handler (for rebuilding projections)."""
        if not self._store:
            return 0
        events = self._store.get_since(since_id, limit=10000)
        for e in events:
            ev = Event(event=e["event"], data=e["data"], src=e["src"],
                       ts=e["ts"], id=e["id"])
            if handler:
                handler(ev)
            else:
                with self._lock:
                    for h in self._global_handlers:
                        try:
                            h(ev)
                        except Exception:
                            logger.exception("Replay handler error for %s", e["event"])
        return len(events)


# ── Singleton bus ─────────────────────────────────────────────────────────────

_bus: EventBus | None = None
_bus_lock = threading.Lock()


def get_bus() -> EventBus:
    """Get or create the global event bus singleton."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = EventBus()
    return _bus


def init_bus(db_module) -> EventBus:
    """Initialize bus with SQLite store from db module."""
    bus = get_bus()
    bus.set_store(SQLiteEventStore(db_module))
    return bus
