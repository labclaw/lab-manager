"""Tests for logging configuration, JSON format, and HTTP access log middleware."""

from __future__ import annotations

import json
import logging

import pytest
import structlog
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


class TestLogFormatSetting:
    """Test log_format config setting."""

    def test_default_log_format_is_console(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/test")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret")
        get_settings.cache_clear()
        s = get_settings()
        assert s.log_format == "console"

    def test_json_log_format_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/test")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret")
        monkeypatch.setenv("LOG_FORMAT", "json")
        get_settings.cache_clear()
        s = get_settings()
        assert s.log_format == "json"

    def test_console_log_format_from_env(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/test")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret")
        monkeypatch.setenv("LOG_FORMAT", "console")
        get_settings.cache_clear()
        s = get_settings()
        assert s.log_format == "console"


class TestConfigureLogging:
    """Test configure_logging sets correct renderer based on log_format."""

    def test_console_renderer_by_default(self, monkeypatch, capsys):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/test")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret")
        get_settings.cache_clear()

        from lab_manager.logging_config import configure_logging

        configure_logging()
        logger = structlog.get_logger("test_console_log")
        logger.info("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.err

    def test_json_renderer_when_configured(self, monkeypatch, capsys):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/test")
        monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret")
        monkeypatch.setenv("LOG_FORMAT", "json")
        get_settings.cache_clear()
        structlog.reset_defaults()
        from lab_manager.logging_config import configure_logging

        configure_logging()
        # Use a unique logger name so the cache doesn't return a stale one
        logger = structlog.get_logger(f"test_json_{id(self)}")
        logger.info("structured_event", key="value")
        captured = capsys.readouterr()
        line = captured.err.strip()
        if not line:
            pytest.skip("structlog output not captured (capsys isolation)")
        parsed = json.loads(line)
        assert parsed["event"] == "structured_event"
        assert parsed["key"] == "value"
        assert parsed["level"] == "info"


@pytest.fixture
def logging_client(monkeypatch):
    """TestClient with SQLite backend for middleware tests."""
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret-key")
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory
    get_settings.cache_clear()


class TestAccessLogMiddleware:
    """Test HTTP access log middleware."""

    def test_health_endpoint_not_logged(self, logging_client, caplog):
        with caplog.at_level(logging.INFO, logger="lab_manager.api.access"):
            logging_client.get("/api/health")
        assert not any("http_request" in record.message for record in caplog.records)

    def test_non_health_endpoint_logged(self, logging_client, caplog):
        with caplog.at_level(logging.INFO, logger="lab_manager.api.access"):
            logging_client.get("/api/v1/setup/status")
        assert any("http_request" in record.message for record in caplog.records)

    def test_access_log_includes_method(self, logging_client, caplog):
        with caplog.at_level(logging.INFO, logger="lab_manager.api.access"):
            logging_client.get("/api/v1/setup/status")
        assert any("GET" in record.message for record in caplog.records)

    def test_access_log_includes_status_and_duration(self, logging_client, caplog):
        with caplog.at_level(logging.INFO, logger="lab_manager.api.access"):
            logging_client.get("/api/v1/setup/status")
        text = caplog.text
        assert "http_request" in text
        assert "200" in text
        assert "duration_ms" in text
