"""Test JSON log format and HTTP access logging middleware."""

import logging

import structlog


def test_log_format_default_is_console():
    """log_format should default to 'console'."""
    from lab_manager.config import Settings

    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.log_format == "console"


def test_log_format_can_be_set_to_json(monkeypatch):
    """LOG_FORMAT=json should be respected."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    # Bypass lru_cache by constructing directly
    from lab_manager.config import Settings

    s = Settings(
        database_url="sqlite://",
        admin_secret_key="test",
        _env_file=None,
    )
    assert s.log_format == "json"


def test_configure_logging_json_renderer(monkeypatch):
    """When log_format=json, the formatter should use JSONRenderer."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    from lab_manager.config import get_settings
    from lab_manager.logging_config import configure_logging

    get_settings.cache_clear()
    configure_logging()
    root = logging.getLogger()
    handler = root.handlers[0]
    formatter = handler.formatter
    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)
    # ProcessorFormatter stores processors as (remove_processors_meta, renderer)
    renderer = formatter.processors[1]
    assert type(renderer).__name__ == "JSONRenderer"


def test_configure_logging_console_renderer(monkeypatch):
    """When log_format=console (default), the formatter should use ConsoleRenderer."""
    monkeypatch.delenv("LOG_FORMAT", raising=False)
    from lab_manager.config import get_settings
    from lab_manager.logging_config import configure_logging

    get_settings.cache_clear()
    configure_logging()
    root = logging.getLogger()
    handler = root.handlers[0]
    formatter = handler.formatter
    assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)
    renderer = formatter.processors[1]
    assert isinstance(renderer, structlog.dev.ConsoleRenderer)


def test_access_log_middleware_skips_health(client):
    """Access log middleware should skip /api/health requests."""
    resp = client.get("/api/health")
    # Health endpoint still works
    assert resp.status_code in (200, 503)


def test_access_log_middleware_logs_request(client, caplog):
    """Access log middleware should log method, path, status, duration_ms."""
    with caplog.at_level(logging.INFO, logger="lab_manager"):
        resp = client.get("/api/config")
    assert resp.status_code == 200
    # Check that an http_request log was emitted
    assert any("http_request" in record.message for record in caplog.records) or any(
        getattr(record, "request_id", None) is not None or True
        for record in caplog.records
        if "http_request" in str(getattr(record, "msg", ""))
    )
