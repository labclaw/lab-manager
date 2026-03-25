"""In-process event bus with optional Redis pub/sub for multi-worker broadcasting.

Enables decoupled communication between services:
- Inventory changes → search re-index, alert checks
- Document processed → analytics update
- Order received → inventory adjustment

Events are dispatched synchronously in-process and optionally published
to Redis pub/sub for cross-worker notification.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event with metadata."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "app"


# Well-known event types
INVENTORY_CHANGED = "inventory.changed"
INVENTORY_LOW_STOCK = "inventory.low_stock"
ORDER_RECEIVED = "order.received"
ORDER_CREATED = "order.created"
DOCUMENT_PROCESSED = "document.processed"
DOCUMENT_REVIEW_NEEDED = "document.review_needed"
VENDOR_UPDATED = "vendor.updated"
PRODUCT_UPDATED = "product.updated"
SEARCH_REINDEX = "search.reindex"
CACHE_INVALIDATE = "cache.invalidate"


# ---------------------------------------------------------------------------
# Event bus (singleton)
# ---------------------------------------------------------------------------


class EventBus:
    """Thread-safe event bus with sync dispatch and optional Redis broadcast."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._redis_enabled = False
        self._subscriber_thread: threading.Thread | None = None

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        """Register a handler for an event type."""
        with self._lock:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug("Subscribed %s to %s", handler.__name__, event_type)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]):
        """Remove a handler."""
        with self._lock:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def publish(self, event: Event):
        """Dispatch event to all registered handlers.

        Handlers run synchronously in the caller's thread. Exceptions in
        one handler do not prevent others from running.
        """
        with self._lock:
            handlers = list(self._handlers.get(event.type, []))
            # Also dispatch to wildcard subscribers
            handlers.extend(self._handlers.get("*", []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Event handler %s failed for %s", handler.__name__, event.type
                )

        # Broadcast to other workers via Redis pub/sub
        if self._redis_enabled:
            self._redis_publish(event)

    def enable_redis_broadcast(self):
        """Enable Redis pub/sub for cross-worker event broadcasting."""
        try:
            from lab_manager.cache import get_redis

            r = get_redis()
            if r is not None:
                self._redis_enabled = True
                self._start_redis_subscriber()
                logger.info("Redis event broadcasting enabled")
        except Exception:
            logger.warning("Could not enable Redis event broadcasting")

    def _redis_publish(self, event: Event):
        """Publish event to Redis pub/sub channel."""
        try:
            import json

            from lab_manager.cache import get_redis

            r = get_redis()
            if r is not None:
                channel = f"lm:events:{event.type}"
                r.publish(
                    channel,
                    json.dumps(
                        {
                            "type": event.type,
                            "data": event.data,
                            "timestamp": event.timestamp,
                            "source": event.source,
                        },
                        default=str,
                    ),
                )
        except Exception:
            logger.debug("Failed to publish event to Redis")

    def _start_redis_subscriber(self):
        """Start background thread to listen for events from other workers."""
        if self._subscriber_thread is not None:
            return

        def _listen():
            import json

            from lab_manager.cache import get_redis

            r = get_redis()
            if r is None:
                return
            try:
                pubsub = r.pubsub()
                pubsub.psubscribe("lm:events:*")
                for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        data = json.loads(message["data"])
                        # Only dispatch events from other sources
                        if data.get("source") != "app":
                            event = Event(
                                type=data["type"],
                                data=data.get("data", {}),
                                timestamp=data.get("timestamp", ""),
                                source=data.get("source", "remote"),
                            )
                            # Dispatch locally without re-broadcasting
                            with self._lock:
                                handlers = list(self._handlers.get(event.type, []))
                                handlers.extend(self._handlers.get("*", []))
                            for handler in handlers:
                                try:
                                    handler(event)
                                except Exception:
                                    logger.exception("Remote event handler failed")
                    except Exception:
                        pass
            except Exception:
                logger.warning("Redis subscriber disconnected")

        self._subscriber_thread = threading.Thread(
            target=_listen, daemon=True, name="event-subscriber"
        )
        self._subscriber_thread.start()

    def clear(self):
        """Remove all handlers (for testing)."""
        with self._lock:
            self._handlers.clear()


# Module-level singleton
_bus = EventBus()


def get_event_bus() -> EventBus:
    """Return the global event bus instance."""
    return _bus


# Convenience functions
def publish(event_type: str, data: dict | None = None, source: str = "app"):
    """Publish an event by type string."""
    _bus.publish(Event(type=event_type, data=data or {}, source=source))


def subscribe(event_type: str, handler: Callable):
    """Subscribe a handler to an event type."""
    _bus.subscribe(event_type, handler)
