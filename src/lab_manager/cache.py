"""Redis-backed caching layer for scalable read performance.

Provides:
- Key-value cache with TTL
- Cache decorator for endpoint responses
- Cache invalidation by prefix/pattern
- Connection pooling with health checks
- Graceful fallback when Redis is unavailable
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis connection singleton
# ---------------------------------------------------------------------------

_redis_client = None
_redis_lock = threading.RLock()
_UNAVAILABLE_UNTIL: float = 0.0  # circuit breaker timestamp
_CIRCUIT_BREAKER_SECONDS = 30  # back off for 30s after failure


def _get_redis():
    """Return a Redis client, or None if unavailable."""
    global _redis_client, _UNAVAILABLE_UNTIL

    # Circuit breaker: skip reconnect attempts for a while after failure
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
            # Verify connection
            _redis_client.ping()
            logger.info("Redis connected: %s", settings.redis_url)
            return _redis_client
        except Exception as exc:
            logger.warning("Redis unavailable, caching disabled: %s", exc)
            _redis_client = None
            _UNAVAILABLE_UNTIL = time.monotonic() + _CIRCUIT_BREAKER_SECONDS
            return None


def get_redis():
    """Public accessor for the Redis client."""
    return _get_redis()


def reset_redis():
    """Reset Redis connection (for testing)."""
    global _redis_client, _UNAVAILABLE_UNTIL
    with _redis_lock:
        if _redis_client is not None:
            try:
                _redis_client.close()
            except Exception:
                pass
        _redis_client = None
        _UNAVAILABLE_UNTIL = 0.0


# ---------------------------------------------------------------------------
# Cache operations
# ---------------------------------------------------------------------------

_KEY_PREFIX = "lm:"


def _make_key(namespace: str, key: str) -> str:
    """Build a namespaced cache key."""
    return f"{_KEY_PREFIX}{namespace}:{key}"


def cache_get(namespace: str, key: str) -> Any | None:
    """Get a cached value. Returns None on miss or if Redis unavailable."""
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(_make_key(namespace, key))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def cache_set(namespace: str, key: str, value: Any, ttl: int = 300) -> bool:
    """Set a cached value with TTL in seconds. Returns True on success."""
    r = _get_redis()
    if r is None:
        return False
    try:
        r.setex(_make_key(namespace, key), ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


def cache_delete(namespace: str, key: str) -> bool:
    """Delete a specific cache key."""
    r = _get_redis()
    if r is None:
        return False
    try:
        r.delete(_make_key(namespace, key))
        return True
    except Exception:
        return False


def cache_invalidate_prefix(namespace: str) -> int:
    """Invalidate all keys under a namespace. Returns count deleted."""
    r = _get_redis()
    if r is None:
        return 0
    try:
        pattern = f"{_KEY_PREFIX}{namespace}:*"
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                deleted += r.delete(*keys)
            if cursor == 0:
                break
        return deleted
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Cache decorator for endpoint responses
# ---------------------------------------------------------------------------


def cached_response(namespace: str, ttl: int = 300, key_builder=None):
    """Decorator that caches JSON-serializable return values.

    Args:
        namespace: Cache namespace (e.g., "vendors", "products").
        ttl: Time-to-live in seconds (default 5 minutes).
        key_builder: Optional callable(args, kwargs) -> str for custom keys.
                     Default builds key from all arguments.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function arguments
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Hash all args for a stable key
                key_parts = [func.__name__]
                for a in args:
                    if hasattr(a, "__class__") and a.__class__.__name__ in (
                        "Request",
                        "Session",
                    ):
                        continue  # Skip non-serializable objects
                    key_parts.append(str(a))
                for k, v in sorted(kwargs.items()):
                    if k in ("request", "db"):
                        continue
                    key_parts.append(f"{k}={v}")
                cache_key = hashlib.md5(
                    "|".join(key_parts).encode()
                ).hexdigest()

            # Try cache first
            cached = cache_get(namespace, cache_key)
            if cached is not None:
                return cached

            # Call function and cache result
            result = func(*args, **kwargs)
            cache_set(namespace, cache_key, result, ttl)
            return result

        # Expose invalidation helper on the wrapper
        wrapper.invalidate_all = lambda: cache_invalidate_prefix(namespace)
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Distributed lock (for coordinating workers)
# ---------------------------------------------------------------------------


class DistributedLock:
    """Simple Redis-based distributed lock with auto-expiry."""

    def __init__(self, name: str, timeout: int = 30):
        self.name = f"{_KEY_PREFIX}lock:{name}"
        self.timeout = timeout
        self._acquired = False

    def acquire(self) -> bool:
        r = _get_redis()
        if r is None:
            return True  # No Redis = no contention, proceed
        try:
            self._acquired = bool(r.set(self.name, "1", nx=True, ex=self.timeout))
            return self._acquired
        except Exception:
            return True

    def release(self):
        if not self._acquired:
            return
        r = _get_redis()
        if r is None:
            return
        try:
            r.delete(self.name)
        except Exception:
            pass
        self._acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


# ---------------------------------------------------------------------------
# Rate counter (for distributed rate limiting across workers)
# ---------------------------------------------------------------------------


def rate_counter_increment(key: str, window: int = 60) -> int:
    """Increment a sliding-window rate counter. Returns current count."""
    r = _get_redis()
    if r is None:
        return 0  # Can't count without Redis
    try:
        full_key = f"{_KEY_PREFIX}rate:{key}"
        pipe = r.pipeline()
        pipe.incr(full_key)
        pipe.expire(full_key, window)
        results = pipe.execute()
        return results[0]
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def cache_health() -> dict[str, str]:
    """Return cache health status."""
    r = _get_redis()
    if r is None:
        return {"redis": "unavailable"}
    try:
        info = r.info(section="memory")
        return {
            "redis": "ok",
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "connected_clients": str(r.info(section="clients").get("connected_clients", "?")),
        }
    except Exception as exc:
        return {"redis": f"error: {exc}"}
