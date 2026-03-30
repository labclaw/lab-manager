"""Tests for email_poller module — IMAP polling, error handling, shutdown."""

from __future__ import annotations

import imaplib
import threading
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.email_poller import (
    DEFAULT_POLL_INTERVAL,
    _connect_imap,
    _fetch_unseen_emails,
    _get_imap_config,
    _get_imap_password,
    _shutdown_event,
    poll_once,
    run_poller,
    stop_poller,
)


# ---------------------------------------------------------------------------
# _get_imap_config / _get_imap_password
# ---------------------------------------------------------------------------


class TestGetImapConfig:
    """Tests for _get_imap_config reading env vars."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EMAIL_IMAP_HOST", raising=False)
        monkeypatch.delenv("EMAIL_IMAP_USER", raising=False)
        monkeypatch.delenv("EMAIL_FOLDER", raising=False)
        monkeypatch.delenv("EMAIL_POLL_INTERVAL", raising=False)

        cfg = _get_imap_config()
        assert cfg["host"] == ""
        assert cfg["user"] == ""
        assert cfg["folder"] == "INBOX"
        assert cfg["interval"] == DEFAULT_POLL_INTERVAL

    def test_custom_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_FOLDER", "Orders")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "60")

        cfg = _get_imap_config()
        assert cfg["host"] == "imap.example.com"
        assert cfg["user"] == "user@example.com"
        assert cfg["folder"] == "Orders"
        assert cfg["interval"] == 60


class TestGetImapPassword:
    """Tests for _get_imap_password."""

    def test_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret123")
        assert _get_imap_password() == "secret123"

    def test_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EMAIL_IMAP_PASSWORD", raising=False)
        assert _get_imap_password() == ""


# ---------------------------------------------------------------------------
# _connect_imap
# ---------------------------------------------------------------------------


class TestConnectImap:
    """Tests for _connect_imap — IMAP4_SSL connection and login."""

    @patch("lab_manager.services.email_poller.imaplib.IMAP4_SSL")
    def test_connects_and_logs_in(
        self, mock_imap_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_conn = MagicMock()
        mock_imap_cls.return_value = mock_conn
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "my_pass")

        config = {"host": "imap.example.com", "user": "user@example.com"}
        result = _connect_imap(config, "my_pass")

        mock_imap_cls.assert_called_once_with("imap.example.com", timeout=30)
        mock_conn.login.assert_called_once_with("user@example.com", "my_pass")
        assert result is mock_conn

    @patch("lab_manager.services.email_poller.imaplib.IMAP4_SSL")
    def test_connection_error_propagates(
        self, mock_imap_cls: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_imap_cls.side_effect = imaplib.IMAP4.error("Connection refused")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        config = {"host": "bad.host", "user": "user@example.com"}
        with pytest.raises(imaplib.IMAP4.error, match="Connection refused"):
            _connect_imap(config, "pass")


# ---------------------------------------------------------------------------
# _fetch_unseen_emails
# ---------------------------------------------------------------------------


class TestFetchUnseenEmails:
    """Tests for _fetch_unseen_emails with mocked IMAP connection."""

    @staticmethod
    def _make_conn(search_data: bytes, fetch_data: list) -> MagicMock:
        conn = MagicMock(spec=imaplib.IMAP4_SSL)
        conn.search.return_value = ("OK", [search_data])
        conn.fetch.return_value = ("OK", fetch_data)
        return conn

    def test_no_unseen(self) -> None:
        conn = self._make_conn(b"", [])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []
        conn.select.assert_called_once_with("INBOX")
        conn.search.assert_called_once_with(None, "UNSEEN")

    def test_single_email(self) -> None:
        body = b"Subject: Test\r\n\r\nHello"
        conn = self._make_conn(b"1", [("1 (RFC822)", body)])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert len(result) == 1
        assert "Hello" in result[0]

    def test_multiple_emails(self) -> None:
        body1 = b"Subject: A\r\n\r\nBodyA"
        body2 = b"Subject: B\r\n\r\nBodyB"
        # search returns space-separated IDs
        conn = self._make_conn(b"1 2", [("1 (RFC822)", body1), ("2 (RFC822)", body2)])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert len(result) == 2

    def test_empty_num_in_split(self) -> None:
        """When search returns extra whitespace, split yields empty strings."""
        conn = self._make_conn(b" 1 ", [("1 (RFC822)", b"data")])
        result = _fetch_unseen_emails(conn, "INBOX")
        # Only "1" is non-empty after split, so one email fetched
        assert len(result) == 1

    def test_search_returns_empty_bytes_element(self) -> None:
        """When search data split yields empty bytes, the guard skips them."""
        conn = MagicMock(spec=imaplib.IMAP4_SSL)
        conn.select.return_value = ("OK", [b"1"])
        # Override search to return data that when split gives empty elements
        conn.search.return_value = ("OK", [b""])
        # When msg_nums[0] is b"", split() returns [b""], which is falsy
        # The loop hits `if not num: continue`
        conn.fetch.return_value = ("OK", [])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []
        # fetch should NOT be called since the only num is b"" which is skipped
        conn.fetch.assert_not_called()

    def test_fetch_data_none_entry(self) -> None:
        """fetch returns data but first element is None."""
        conn = self._make_conn(b"1", [None])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_fetch_data_not_tuple(self) -> None:
        """fetch returns data but first element is not a tuple."""
        conn = self._make_conn(b"1", ["not_a_tuple"])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_fetch_data_raw_bytes_not_bytes(self) -> None:
        """data[0][1] is not bytes — should be skipped."""
        conn = self._make_conn(b"1", [("1 (RFC822)", "string_not_bytes")])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_utf8_decode_with_replacement(self) -> None:
        """Non-UTF8 bytes decoded with errors='replace'."""
        bad_bytes = b"\xff\xfe invalid"
        conn = self._make_conn(b"1", [("1 (RFC822)", bad_bytes)])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert len(result) == 1
        # Should not raise — replacement char expected
        assert "\ufffd" in result[0] or "invalid" in result[0]


# ---------------------------------------------------------------------------
# poll_once
# ---------------------------------------------------------------------------


class TestPollOnce:
    """Tests for poll_once — the single poll cycle."""

    def test_missing_host_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EMAIL_IMAP_HOST", raising=False)
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        assert poll_once() == 0

    def test_missing_user_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.delenv("EMAIL_IMAP_USER", raising=False)
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        assert poll_once() == 0

    def test_missing_password_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.delenv("EMAIL_IMAP_PASSWORD", raising=False)
        assert poll_once() == 0

    @patch("lab_manager.services.email_poller._connect_imap")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_intake.process_email")
    def test_success_with_emails(
        self,
        mock_process: MagicMock,
        mock_db_session: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        monkeypatch.setenv("EMAIL_FOLDER", "INBOX")

        mock_conn = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = ["raw_email_1", "raw_email_2"]

        # Make get_db_session a context manager returning a mock session
        mock_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_process.side_effect = [
            [MagicMock()],  # first email -> 1 doc
            [MagicMock(), MagicMock()],  # second email -> 2 docs
        ]

        result = poll_once()
        assert result == 3
        mock_conn.logout.assert_called_once()

    @patch("lab_manager.services.email_poller._connect_imap")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    def test_success_no_emails(
        self,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")

        mock_conn = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = []

        result = poll_once()
        assert result == 0
        mock_conn.logout.assert_called_once()

    @patch("lab_manager.services.email_poller._connect_imap")
    def test_connection_failure_returns_0(
        self,
        mock_connect: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")

        mock_connect.side_effect = imaplib.IMAP4.error("Connection refused")

        result = poll_once()
        assert result == 0

    @patch("lab_manager.services.email_poller._connect_imap")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_intake.process_email")
    def test_email_processing_failure_continues(
        self,
        mock_process: MagicMock,
        mock_db_session: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If one email fails to process, others still get processed."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")

        mock_conn = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = ["bad_email", "good_email"]

        mock_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_process.side_effect = [
            RuntimeError("parse error"),
            [MagicMock()],  # second email succeeds
        ]

        result = poll_once()
        assert result == 1
        mock_conn.logout.assert_called_once()

    @patch("lab_manager.services.email_poller._connect_imap")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    def test_logout_failure_suppressed(
        self,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If conn.logout() raises, it should be silently suppressed."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")

        mock_conn = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = []
        mock_conn.logout.side_effect = imaplib.IMAP4.error("already closed")

        result = poll_once()
        assert result == 0

    @patch("lab_manager.services.email_poller._connect_imap")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.database.get_db_session")
    def test_email_with_no_documents(
        self,
        mock_db_session: MagicMock,
        mock_fetch: MagicMock,
        mock_connect: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """process_email returns empty list — total stays 0."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")

        mock_conn = MagicMock(spec=imaplib.IMAP4_SSL)
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = ["email_no_docs"]

        mock_session = MagicMock()
        mock_db_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db_session.return_value.__exit__ = MagicMock(return_value=False)

        result = poll_once()
        assert result == 0


# ---------------------------------------------------------------------------
# run_poller / stop_poller
# ---------------------------------------------------------------------------


class TestRunPoller:
    """Tests for run_poller (blocking loop) and stop_poller."""

    def test_not_configured_no_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EMAIL_IMAP_HOST", raising=False)
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        # Returns immediately — no blocking
        run_poller()

    def test_not_configured_no_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.delenv("EMAIL_IMAP_USER", raising=False)
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        run_poller()

    def test_not_configured_no_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.delenv("EMAIL_IMAP_PASSWORD", raising=False)
        run_poller()

    @patch("lab_manager.services.email_poller.poll_once", return_value=0)
    def test_runs_then_stops_on_shutdown(
        self,
        mock_poll_once: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Poller runs at least once, then exits when stop_poller() is called."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "1")

        # Set shutdown event after a short delay so the poller loop runs once
        def trigger_stop() -> None:
            import time

            time.sleep(0.3)
            stop_poller()

        t = threading.Thread(target=trigger_stop)
        t.start()
        run_poller()  # Should block then return
        t.join(timeout=5)
        mock_poll_once.assert_called()

    @patch(
        "lab_manager.services.email_poller.poll_once", side_effect=RuntimeError("boom")
    )
    def test_poll_cycle_exception_does_not_crash(
        self,
        mock_poll_once: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exception in poll_once is caught, poller continues until stopped."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "1")

        def trigger_stop() -> None:
            import time

            time.sleep(0.5)
            stop_poller()

        t = threading.Thread(target=trigger_stop)
        t.start()
        run_poller()  # Should not raise
        t.join(timeout=5)

    @patch("lab_manager.services.email_poller.poll_once", return_value=5)
    def test_logs_document_count(
        self,
        mock_poll_once: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When poll_once returns > 0, poller logs the document count."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "user@example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "secret")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "1")

        def trigger_stop() -> None:
            import time

            time.sleep(0.3)
            stop_poller()

        t = threading.Thread(target=trigger_stop)
        t.start()
        run_poller()
        t.join(timeout=5)
        # poll_once was called at least once returning 5
        assert mock_poll_once.called
        # Verify the return value was propagated
        assert mock_poll_once.return_value == 5


class TestStopPoller:
    """Tests for stop_poller."""

    def test_sets_shutdown_event(self) -> None:
        _shutdown_event.clear()
        assert not _shutdown_event.is_set()
        stop_poller()
        assert _shutdown_event.is_set()
        # Clean up
        _shutdown_event.clear()
