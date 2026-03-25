"""Redis cache layer with graceful fallback when unavailable."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_redis_client = None
_redis_lock = threading.RLock()
_UNAVAILABLE_UNTIL: float = 0.0
_CIRCUIT_BREAKER_SECONDS = 30
_KEY_PREFIX = "lm:"


def get_redis():
    """Return a Redis client, or None if unavailable."""
    global _redis_client, _UNAVAILABLE_UNTIL

    if _UNAVAILABLE_UNTIL > time.monotonic():
        return None
    if _redis_client is not None:
        return _redis_client

    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis

            from lab_manager.config import get_settings

            settings = get_settings()
            _redis_client = redis.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                max_connections=settings.redis_max_connections,
                health_check_interval=30,
            )
            _redis_client.ping()
            logger.info("Redis connected: %s", settings.redis_url)
            return _redis_client
        except Exception as exc:
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            _redis_client = None
            _UNAVAILABLE_UNTIL = time.monotonic() + _CIRCUIT_BREAKER_SECONDS
            return None


def reset_redis():
    """Reset connection (for testing)."""
    global _redis_client, _UNAVAILABLE_UNTIL
    with _redis_lock:
        if _redis_client is not None:
            try:
                _redis_client.close()
            except Exception:
                pass
        _redis_client = None
        _UNAVAILABLE_UNTIL = 0.0


def cache_get(namespace: str, key: str) -> Any | None:
    """Get a value. Returns None on miss or if Redis unavailable."""
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(f"{_KEY_PREFIX}{namespace}:{key}")
        return json.loads(raw) if raw is not None else None
    except Exception:
        return None


def cache_set(namespace: str, key: str, value: Any, ttl: int = 300) -> bool:
    """Set a value with TTL in seconds."""
    r = get_redis()
    if r is None:
        return False
    try:
        r.setex(f"{_KEY_PREFIX}{namespace}:{key}", ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def cache_delete(namespace: str, key: str) -> bool:
    """Delete a cache key."""
    r = get_redis()
    if r is None:
        return False
    try:
        r.delete(f"{_KEY_PREFIX}{namespace}:{key}")
        return True
    except Exception:
        return False


def cache_health() -> dict[str, str]:
    """Return Redis health for /api/health."""
    r = get_redis()
    if r is None:
        return {"redis": "unavailable"}
    try:
        info = r.info(section="memory")
        return {
            "redis": "ok",
            "used_memory_human": info.get("used_memory_human", "unknown"),
        }
    except Exception as exc:
        return {"redis": f"error: {exc}"}
