"""Tests for logging_config: request_id generation, structlog setup."""

import logging

import structlog

from lab_manager.logging_config import (
    add_request_id,
    configure_logging,
    generate_request_id,
    request_id_var,
)


# ---------------------------------------------------------------------------
# request_id context variable
# ---------------------------------------------------------------------------


class TestRequestIdVar:
    """Tests for the request_id context variable."""

    def test_default_is_none(self):
        """Unset request_id defaults to None."""
        request_id_var.set(None)
        assert request_id_var.get() is None

    def test_set_and_get(self):
        """request_id_var stores and retrieves a value."""
        request_id_var.set("abc123")
        assert request_id_var.get() == "abc123"
        request_id_var.set(None)  # cleanup


# ---------------------------------------------------------------------------
# generate_request_id
# ---------------------------------------------------------------------------


class TestGenerateRequestId:
    """Tests for generate_request_id()."""

    def test_returns_string(self):
        rid = generate_request_id()
        assert isinstance(rid, str)

    def test_length_12(self):
        """Request ID is a 12-char hex string (uuid4 hex truncated)."""
        rid = generate_request_id()
        assert len(rid) == 12

    def test_hex_characters_only(self):
        """Only hex characters [0-9a-f]."""
        rid = generate_request_id()
        assert all(c in "0123456789abcdef" for c in rid)

    def test_stores_in_context_var(self):
        """generate_request_id sets the context variable."""
        rid = generate_request_id()
        assert request_id_var.get() == rid

    def test_unique_across_calls(self):
        """Successive calls produce different IDs."""
        rid1 = generate_request_id()
        rid2 = generate_request_id()
        assert rid1 != rid2

    def test_overwrites_previous(self):
        """Each call overwrites the previous request_id."""
        rid1 = generate_request_id()
        rid2 = generate_request_id()
        assert request_id_var.get() == rid2
        assert request_id_var.get() != rid1


# ---------------------------------------------------------------------------
# add_request_id processor
# ---------------------------------------------------------------------------


class TestAddRequestId:
    """Tests for the structlog add_request_id processor."""

    def test_adds_request_id_when_set(self):
        """If request_id_var is set, it is injected into the event dict."""
        request_id_var.set("test-rid-123")
        event = add_request_id("test", "info", {"event": "hello"})
        assert event["request_id"] == "test-rid-123"
        request_id_var.set(None)

    def test_no_request_id_when_unset(self):
        """If request_id_var is None, no key is added."""
        request_id_var.set(None)
        event = add_request_id("test", "info", {"event": "hello"})
        assert "request_id" not in event

    def test_preserves_existing_keys(self):
        """Processor does not remove existing event dict entries."""
        request_id_var.set("abc")
        event = add_request_id("test", "info", {"event": "msg", "key": "val"})
        assert event["event"] == "msg"
        assert event["key"] == "val"
        assert event["request_id"] == "abc"
        request_id_var.set(None)


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def test_configures_structlog(self):
        """After configure_logging, structlog is properly configured."""
        configure_logging()
        # structlog.get_logger should work without error
        log = structlog.get_logger("test")
        assert log is not None

    def test_sets_root_logger_level(self):
        """Root logger level is set to INFO."""
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_clears_old_handlers(self):
        """configure_logging clears existing handlers before adding its own."""
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())
        count_before = len(root.handlers)

        configure_logging()
        count_after = len(root.handlers)
        assert count_after == 1  # only the new handler
        assert count_after < count_before + 1  # old handlers gone

    def test_quiets_uvicorn_access(self):
        """uvicorn.access logger is set to WARNING."""
        configure_logging()
        assert logging.getLogger("uvicorn.access").level == logging.WARNING

    def test_quiets_sqlalchemy_engine(self):
        """sqlalchemy.engine logger is set to WARNING."""
        configure_logging()
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
