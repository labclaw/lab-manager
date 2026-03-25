"""Prometheus-compatible metrics collection middleware.

Collects:
- Request count by method, path, status
- Request duration histogram
- Active connections gauge
- Database pool stats
- Cache hit/miss ratio
- Task queue depth

Exposes metrics at /metrics in Prometheus text format.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from fastapi import Request
from starlette.responses import PlainTextResponse, Response


class MetricsCollector:
    """Thread-safe metrics collector for Prometheus exposition."""

    def __init__(self):
        self._lock = threading.RLock()
        # Counters
        self.request_count: dict[str, int] = defaultdict(int)
        self.request_errors: dict[str, int] = defaultdict(int)
        # Histograms (simplified: track sum and count for avg)
        self.request_duration_sum: dict[str, float] = defaultdict(float)
        self.request_duration_count: dict[str, int] = defaultdict(int)
        # Gauges
        self.active_connections = 0
        self.db_pool_size = 0
        self.db_pool_checked_out = 0
        self.task_queue_depth = 0
        self.cache_hits = 0
        self.cache_misses = 0
        # Duration buckets
        self._buckets = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.request_duration_buckets: dict[str, dict[float, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def record_request(self, method: str, path: str, status: int, duration: float):
        """Record a completed request."""
        # Normalize path to reduce cardinality
        normalized = self._normalize_path(path)
        key = f'{method}|{normalized}|{status}'

        with self._lock:
            self.request_count[key] += 1
            if status >= 400:
                self.request_errors[f'{method}|{normalized}|{status}'] += 1
            self.request_duration_sum[f'{method}|{normalized}'] += duration
            self.request_duration_count[f'{method}|{normalized}'] += 1
            # Bucket the duration
            bucket_key = f'{method}|{normalized}'
            for bucket in self._buckets:
                if duration <= bucket:
                    self.request_duration_buckets[bucket_key][bucket] += 1

    def update_db_pool(self, size: int, checked_out: int):
        """Update database pool gauges."""
        with self._lock:
            self.db_pool_size = size
            self.db_pool_checked_out = checked_out

    def record_cache_hit(self):
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self):
        with self._lock:
            self.cache_misses += 1

    def format_prometheus(self) -> str:
        """Format all metrics in Prometheus text exposition format."""
        lines = []

        with self._lock:
            # Request count
            lines.append("# HELP labmanager_http_requests_total Total HTTP requests")
            lines.append("# TYPE labmanager_http_requests_total counter")
            for key, count in sorted(self.request_count.items()):
                method, path, status = key.split("|")
                lines.append(
                    f'labmanager_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            # Request duration
            lines.append(
                "# HELP labmanager_http_request_duration_seconds HTTP request duration"
            )
            lines.append("# TYPE labmanager_http_request_duration_seconds histogram")
            for key in sorted(self.request_duration_sum.keys()):
                method, path = key.split("|")
                total = self.request_duration_sum[key]
                count = self.request_duration_count[key]
                # Buckets
                bucket_key = key
                cumulative = 0
                for bucket in self._buckets:
                    cumulative += self.request_duration_buckets[bucket_key].get(
                        bucket, 0
                    )
                    lines.append(
                        f'labmanager_http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="{bucket}"}} {cumulative}'
                    )
                lines.append(
                    f'labmanager_http_request_duration_seconds_bucket{{method="{method}",path="{path}",le="+Inf"}} {count}'
                )
                lines.append(
                    f'labmanager_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {total:.6f}'
                )
                lines.append(
                    f'labmanager_http_request_duration_seconds_count{{method="{method}",path="{path}"}} {count}'
                )

            # Active connections
            lines.append(
                "# HELP labmanager_active_connections Current active connections"
            )
            lines.append("# TYPE labmanager_active_connections gauge")
            lines.append(f"labmanager_active_connections {self.active_connections}")

            # DB pool
            lines.append("# HELP labmanager_db_pool_size Database connection pool size")
            lines.append("# TYPE labmanager_db_pool_size gauge")
            lines.append(f"labmanager_db_pool_size {self.db_pool_size}")
            lines.append(
                "# HELP labmanager_db_pool_checked_out Database connections in use"
            )
            lines.append("# TYPE labmanager_db_pool_checked_out gauge")
            lines.append(
                f"labmanager_db_pool_checked_out {self.db_pool_checked_out}"
            )

            # Cache
            lines.append("# HELP labmanager_cache_hits_total Cache hits")
            lines.append("# TYPE labmanager_cache_hits_total counter")
            lines.append(f"labmanager_cache_hits_total {self.cache_hits}")
            lines.append("# HELP labmanager_cache_misses_total Cache misses")
            lines.append("# TYPE labmanager_cache_misses_total counter")
            lines.append(f"labmanager_cache_misses_total {self.cache_misses}")

            # Task queue
            lines.append("# HELP labmanager_task_queue_depth Pending tasks in queue")
            lines.append("# TYPE labmanager_task_queue_depth gauge")
            lines.append(f"labmanager_task_queue_depth {self.task_queue_depth}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Reduce path cardinality by replacing IDs with :id."""
        parts = path.rstrip("/").split("/")
        normalized = []
        for part in parts:
            if part.isdigit():
                normalized.append(":id")
            else:
                normalized.append(part)
        return "/".join(normalized)


# Module-level singleton
_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _collector


async def metrics_middleware(request: Request, call_next) -> Response:
    """Collect request metrics."""
    if request.url.path == "/metrics":
        return await call_next(request)

    _collector.active_connections += 1
    start = time.monotonic()
    try:
        response = await call_next(request)
        duration = time.monotonic() - start
        _collector.record_request(
            request.method, request.url.path, response.status_code, duration
        )
        return response
    except Exception:
        duration = time.monotonic() - start
        _collector.record_request(request.method, request.url.path, 500, duration)
        raise
    finally:
        _collector.active_connections -= 1


def metrics_endpoint(request: Request) -> PlainTextResponse:
    """Prometheus metrics endpoint handler."""
    # Update DB pool stats
    try:
        from lab_manager.database import get_engine

        pool = get_engine().pool
        _collector.update_db_pool(pool.size(), pool.checkedout())
    except Exception:
        pass

    # Update task queue depth
    try:
        from lab_manager.cache import get_redis

        r = get_redis()
        if r:
            _collector.task_queue_depth = r.zcard("lm:task_queue") or 0
    except Exception:
        pass

    return PlainTextResponse(
        _collector.format_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
