"""Tests for scalability components: cache, events, tasks, middleware, metrics."""

from __future__ import annotations

import time
from unittest.mock import MagicMock


# ============================================================
# Event bus tests
# ============================================================


class TestEventBus:
    def test_subscribe_and_publish(self):
        from lab_manager.events import Event, EventBus

        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("test.event", handler)
        bus.publish(Event(type="test.event", data={"key": "value"}))

        assert len(received) == 1
        assert received[0].data == {"key": "value"}

    def test_wildcard_subscriber(self):
        from lab_manager.events import Event, EventBus

        bus = EventBus()
        received = []

        bus.subscribe("*", lambda e: received.append(e))
        bus.publish(Event(type="foo"))
        bus.publish(Event(type="bar"))

        assert len(received) == 2

    def test_handler_exception_doesnt_stop_others(self):
        from lab_manager.events import Event, EventBus

        bus = EventBus()
        results = []

        def bad_handler(event):
            raise ValueError("boom")

        def good_handler(event):
            results.append("ok")

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        bus.publish(Event(type="test"))

        assert results == ["ok"]

    def test_unsubscribe(self):
        from lab_manager.events import Event, EventBus

        bus = EventBus()
        received = []
        def handler(e):
            received.append(e)

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        bus.publish(Event(type="test"))

        assert len(received) == 0

    def test_clear(self):
        from lab_manager.events import EventBus

        bus = EventBus()
        bus.subscribe("test", lambda e: None)
        bus.clear()
        assert len(bus._handlers) == 0

    def test_publish_convenience(self):
        """Test module-level publish/subscribe convenience functions."""
        from lab_manager import events

        received = []
        events.subscribe("conv.test", lambda e: received.append(e.data))
        events.publish("conv.test", {"msg": "hello"})

        assert len(received) == 1
        assert received[0] == {"msg": "hello"}

        # Cleanup
        events.get_event_bus().clear()


# ============================================================
# Cache tests (mock Redis)
# ============================================================


class TestCacheOperations:
    def test_cache_get_set_without_redis(self):
        """Cache operations gracefully return None/False without Redis."""
        from lab_manager.cache import cache_get, cache_set

        # With no Redis running, operations should not raise
        result = cache_get("test", "key1")
        assert result is None

        success = cache_set("test", "key1", {"data": 1})
        assert success is False

    def test_cache_get_set_with_mock_redis(self):
        """Cache operations work with a mock Redis client."""
        import lab_manager.cache as cache_mod

        mock_redis = MagicMock()
        store = {}

        def mock_get(key):
            return store.get(key)

        def mock_setex(key, ttl, value):
            store[key] = value

        mock_redis.get = mock_get
        mock_redis.setex = mock_setex

        # Patch the module-level getter
        original_get = cache_mod._get_redis
        cache_mod._get_redis = lambda: mock_redis
        try:
            from lab_manager.cache import cache_get, cache_set

            cache_set("ns", "k1", {"x": 42}, ttl=60)
            result = cache_get("ns", "k1")
            assert result == {"x": 42}
        finally:
            cache_mod._get_redis = original_get

    def test_cached_response_decorator(self):
        """cached_response decorator caches function return values."""
        import lab_manager.cache as cache_mod

        mock_redis = MagicMock()
        store = {}

        def mock_get(key):
            return store.get(key)

        def mock_setex(key, ttl, value):
            store[key] = value

        mock_redis.get = mock_get
        mock_redis.setex = mock_setex

        original_get = cache_mod._get_redis
        cache_mod._get_redis = lambda: mock_redis
        try:
            from lab_manager.cache import cached_response

            call_count = 0

            @cached_response("test", ttl=60)
            def expensive_fn(x: int):
                nonlocal call_count
                call_count += 1
                return {"result": x * 2}

            # First call: computes
            result1 = expensive_fn(5)
            assert result1 == {"result": 10}
            assert call_count == 1

            # Second call: cached
            result2 = expensive_fn(5)
            assert result2 == {"result": 10}
            assert call_count == 1  # Not called again
        finally:
            cache_mod._get_redis = original_get

    def test_distributed_lock_without_redis(self):
        """Lock works (always acquires) when Redis is unavailable."""
        from lab_manager.cache import DistributedLock

        lock = DistributedLock("test-lock", timeout=5)
        assert lock.acquire() is True
        lock.release()

    def test_distributed_lock_context_manager(self):
        from lab_manager.cache import DistributedLock

        with DistributedLock("ctx-lock"):
            pass  # Should not raise

    def test_cache_health_without_redis(self):
        from lab_manager.cache import cache_health

        result = cache_health()
        assert "redis" in result

    def test_rate_counter_without_redis(self):
        from lab_manager.cache import rate_counter_increment

        count = rate_counter_increment("test_key")
        assert count == 0  # No Redis = 0


# ============================================================
# Task system tests
# ============================================================


class TestTaskSystem:
    def test_task_manager_register_and_submit(self):
        from lab_manager.tasks.worker import TaskManager, TaskStatus

        tm = TaskManager(max_workers=2, redis_queue=False)
        results = []

        def my_task(value=0):
            results.append(value)
            return {"computed": value * 2}

        tm.register("my_task", my_task)
        tm.start()
        try:
            task_id = tm.submit("my_task", {"value": 42})
            # Wait for completion
            time.sleep(0.5)
            status = tm.get_status(task_id)
            assert status is not None
            assert status.status == TaskStatus.COMPLETED
            assert results == [42]
        finally:
            tm.stop()

    def test_task_retry_on_failure(self):
        from lab_manager.tasks.worker import TaskManager, TaskStatus

        tm = TaskManager(max_workers=1, redis_queue=False)
        attempts = []

        def flaky_task():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("not yet")
            return "success"

        tm.register("flaky", flaky_task)
        tm.start()
        try:
            task_id = tm.submit(
                "flaky", max_retries=3, timeout=30
            )
            # Wait for retries (with exponential backoff)
            time.sleep(8)
            status = tm.get_status(task_id)
            assert status is not None
            assert status.status == TaskStatus.COMPLETED
            assert len(attempts) == 3
        finally:
            tm.stop()

    def test_unknown_task_fails(self):
        from lab_manager.tasks.worker import TaskManager, TaskStatus

        tm = TaskManager(max_workers=1, redis_queue=False)
        tm.start()
        try:
            task_id = tm.submit("nonexistent")
            time.sleep(0.5)
            status = tm.get_status(task_id)
            assert status.status == TaskStatus.FAILED
        finally:
            tm.stop()

    def test_task_priority_enum(self):
        from lab_manager.tasks import TaskCategory, TaskPriority

        assert TaskPriority.CRITICAL < TaskPriority.HIGH
        assert TaskPriority.HIGH < TaskPriority.NORMAL
        assert TaskCategory.DOCUMENT == "document"


# ============================================================
# Metrics tests
# ============================================================


class TestMetrics:
    def test_metrics_collector_record(self):
        from lab_manager.middleware.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.record_request("GET", "/api/v1/vendors", 200, 0.05)
        mc.record_request("GET", "/api/v1/vendors", 200, 0.03)
        mc.record_request("POST", "/api/v1/vendors", 201, 0.1)
        mc.record_request("GET", "/api/v1/vendors/123", 404, 0.02)

        output = mc.format_prometheus()
        assert "labmanager_http_requests_total" in output
        assert "labmanager_http_request_duration_seconds" in output
        assert "labmanager_active_connections" in output
        assert "labmanager_db_pool_size" in output

    def test_metrics_path_normalization(self):
        from lab_manager.middleware.metrics import MetricsCollector

        assert MetricsCollector._normalize_path("/api/v1/vendors/123") == "/api/v1/vendors/:id"
        assert MetricsCollector._normalize_path("/api/v1/orders/456/items") == "/api/v1/orders/:id/items"
        assert MetricsCollector._normalize_path("/api/health") == "/api/health"

    def test_metrics_cache_counters(self):
        from lab_manager.middleware.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.record_cache_hit()
        mc.record_cache_hit()
        mc.record_cache_miss()

        output = mc.format_prometheus()
        assert "labmanager_cache_hits_total 2" in output
        assert "labmanager_cache_misses_total 1" in output

    def test_metrics_db_pool_update(self):
        from lab_manager.middleware.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.update_db_pool(size=10, checked_out=3)
        assert mc.db_pool_size == 10
        assert mc.db_pool_checked_out == 3


# ============================================================
# Connection limiter tests
# ============================================================


class TestConnectionLimiter:
    def test_limiter_properties(self):
        from lab_manager.middleware.connection_limit import ConnectionLimiter

        limiter = ConnectionLimiter(max_concurrent=50)
        assert limiter.max_concurrent == 50
        assert limiter.current == 0


# ============================================================
# Config scalability settings tests
# ============================================================


class TestScalabilityConfig:
    def test_default_redis_url(self):
        from lab_manager.config import Settings

        s = Settings(admin_secret_key="test")
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.redis_max_connections == 20
        assert s.task_workers == 4
        assert s.max_concurrent_requests == 200
        assert s.db_pool_size == 10
        assert s.db_pool_max_overflow == 20
        assert s.metrics_enabled is True

    def test_custom_scalability_settings(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://custom:6380/1")
        monkeypatch.setenv("TASK_WORKERS", "8")
        monkeypatch.setenv("MAX_CONCURRENT_REQUESTS", "500")
        monkeypatch.setenv("DB_POOL_SIZE", "20")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test")

        from lab_manager.config import Settings

        s = Settings()
        assert s.redis_url == "redis://custom:6380/1"
        assert s.task_workers == 8
        assert s.max_concurrent_requests == 500
        assert s.db_pool_size == 20
