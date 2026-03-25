"""Tests for scalability: Redis cache layer and database pool config."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestCacheOperations:
    def test_cache_get_set_without_redis(self):
        """Cache operations gracefully return None/False without Redis."""
        from lab_manager.cache import cache_get, cache_set

        assert cache_get("test", "key1") is None
        assert cache_set("test", "key1", {"data": 1}) is False

    def test_cache_get_set_with_mock_redis(self):
        """Cache operations work with a mock Redis client."""
        import lab_manager.cache as cache_mod

        mock_redis = MagicMock()
        store = {}
        mock_redis.get = lambda key: store.get(key)
        mock_redis.setex = lambda key, ttl, value: store.__setitem__(key, value)

        original = cache_mod.get_redis
        cache_mod.get_redis = lambda: mock_redis
        try:
            cache_mod.cache_set("ns", "k1", {"x": 42}, ttl=60)
            assert cache_mod.cache_get("ns", "k1") == {"x": 42}
        finally:
            cache_mod.get_redis = original

    def test_cache_delete_without_redis(self):
        from lab_manager.cache import cache_delete

        assert cache_delete("ns", "key") is False

    def test_cache_health_without_redis(self):
        from lab_manager.cache import cache_health

        result = cache_health()
        assert result["redis"] == "unavailable"


class TestScalabilityConfig:
    def test_default_redis_url(self):
        from lab_manager.config import Settings

        s = Settings(admin_secret_key="test")
        assert s.redis_url == "redis://localhost:6379/0"
        assert s.redis_max_connections == 20
        assert s.db_pool_size == 10
        assert s.db_pool_max_overflow == 20
        assert s.db_pool_timeout == 30
        assert s.db_pool_recycle == 1800
        assert s.db_statement_timeout == 30000

    def test_custom_redis_url(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://custom:6380/1")
        monkeypatch.setenv("DB_POOL_SIZE", "20")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test")

        from lab_manager.config import Settings

        s = Settings()
        assert s.redis_url == "redis://custom:6380/1"
        assert s.db_pool_size == 20
