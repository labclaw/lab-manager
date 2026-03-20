"""Test configuration loading."""


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/testdb")
    monkeypatch.setenv("MEILISEARCH_URL", "http://localhost:7700")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret")
    from lab_manager.config import get_settings

    s = get_settings.cache_clear()
    s = get_settings()
    assert "testdb" in s.database_url
    assert s.meilisearch_url == "http://localhost:7700"


def test_database_url_normalization():
    """DO App Platform provides postgresql:// but SQLAlchemy needs postgresql+psycopg://."""
    from lab_manager.config import Settings

    s = Settings(
        database_url="postgresql://user:pass@host:5432/db", admin_secret_key="test"
    )
    assert s.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_database_url_already_normalized():
    """URLs with +psycopg should not be double-prefixed."""
    from lab_manager.config import Settings

    s = Settings(
        database_url="postgresql+psycopg://user:pass@host:5432/db",
        admin_secret_key="test",
    )
    assert s.database_url == "postgresql+psycopg://user:pass@host:5432/db"
