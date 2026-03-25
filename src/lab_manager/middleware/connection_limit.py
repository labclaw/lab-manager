"""Connection limiting middleware to prevent overload.

Implements a semaphore-based concurrency limiter that rejects requests
with 503 when the server is at capacity. This prevents cascading failures
under load and ensures existing requests complete successfully.
"""

from __future__ import annotations

import threading

from fastapi import Request
from starlette.responses import JSONResponse, Response


class ConnectionLimiter:
    """Limits concurrent request processing."""

    def __init__(self, max_concurrent: int = 200):
        self._semaphore = threading.Semaphore(max_concurrent)
        self._max = max_concurrent
        self._current = 0
        self._lock = threading.Lock()

    @property
    def current(self) -> int:
        return self._current

    @property
    def max_concurrent(self) -> int:
        return self._max

    async def __call__(self, request: Request, call_next) -> Response:
        # Always allow health checks through
        if request.url.path in ("/api/health", "/metrics"):
            return await call_next(request)

        acquired = self._semaphore.acquire(blocking=False)
        if not acquired:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Server at capacity. Please retry shortly.",
                    "retry_after": 5,
                },
                headers={"Retry-After": "5"},
            )

        with self._lock:
            self._current += 1
        try:
            return await call_next(request)
        finally:
            with self._lock:
                self._current -= 1
            self._semaphore.release()


_limiter: ConnectionLimiter | None = None


def get_connection_limiter(max_concurrent: int = 200) -> ConnectionLimiter:
    global _limiter
    if _limiter is None:
        _limiter = ConnectionLimiter(max_concurrent)
    return _limiter
