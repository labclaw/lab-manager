"""Test configuration loading."""


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/testdb")
    monkeypatch.setenv("MEILISEARCH_URL", "http://localhost:7700")
    from lab_manager.config import get_settings

    s = get_settings.cache_clear()
    s = get_settings()
    assert "testdb" in s.database_url
    assert s.meilisearch_url == "http://localhost:7700"
