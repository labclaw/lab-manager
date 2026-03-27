"""Tests for the IMAP email poller service.

Covers: _get_imap_config, _get_imap_password, _connect_imap,
_fetch_unseen_emails, poll_once, run_poller.
"""

from __future__ import annotations

from contextlib import contextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.email_poller import (
    DEFAULT_POLL_INTERVAL,
    _connect_imap,
    _fetch_unseen_emails,
    _get_imap_config,
    _get_imap_password,
    poll_once,
    run_poller,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no leftover IMAP env vars leak between tests."""
    monkeypatch.delenv("EMAIL_IMAP_HOST", raising=False)
    monkeypatch.delenv("EMAIL_IMAP_USER", raising=False)
    monkeypatch.delenv("EMAIL_IMAP_PASSWORD", raising=False)
    monkeypatch.delenv("EMAIL_FOLDER", raising=False)
    monkeypatch.delenv("EMAIL_POLL_INTERVAL", raising=False)


# ---------------------------------------------------------------------------
# _get_imap_config
# ---------------------------------------------------------------------------


class TestGetImapConfig:
    """Test _get_imap_config reads environment variables correctly."""

    def test_defaults_when_unset(self):
        """Returns empty host/user and default folder/interval when env unset."""
        config = _get_imap_config()
        assert config["host"] == ""
        assert config["user"] == ""
        assert config["folder"] == "INBOX"
        assert config["interval"] == DEFAULT_POLL_INTERVAL

    def test_reads_all_values_from_env(self, monkeypatch):
        """Reads host, user, folder, interval from environment."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.gmail.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@example.com")
        monkeypatch.setenv("EMAIL_FOLDER", "Inbox")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "60")

        config = _get_imap_config()
        assert config["host"] == "imap.gmail.com"
        assert config["user"] == "lab@example.com"
        assert config["folder"] == "Inbox"
        assert config["interval"] == 60

    def test_partial_env_keeps_defaults(self, monkeypatch):
        """Only set host; user stays empty, folder/interval keep defaults."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")

        config = _get_imap_config()
        assert config["host"] == "imap.example.com"
        assert config["user"] == ""
        assert config["folder"] == "INBOX"
        assert config["interval"] == DEFAULT_POLL_INTERVAL


# ---------------------------------------------------------------------------
# _get_imap_password
# ---------------------------------------------------------------------------


class TestGetImapPassword:
    """Test _get_imap_password reads password env var."""

    def test_returns_empty_when_unset(self):
        assert _get_imap_password() == ""

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "s3cret")
        assert _get_imap_password() == "s3cret"


# ---------------------------------------------------------------------------
# _connect_imap
# ---------------------------------------------------------------------------


class TestConnectImap:
    """Test _connect_imap creates IMAP4_SSL connection and logs in."""

    @patch("lab_manager.services.email_poller.imaplib.IMAP4_SSL")
    def test_connects_and_logs_in(self, mock_imap_cls):
        """Creates IMAP4_SSL with host and calls login with user/password."""
        mock_instance = MagicMock()
        mock_imap_cls.return_value = mock_instance

        config = {"host": "imap.example.com", "user": "lab@test.com"}
        result = _connect_imap(config, "pass123")

        mock_imap_cls.assert_called_once_with("imap.example.com")
        mock_instance.login.assert_called_once_with("lab@test.com", "pass123")
        assert result is mock_instance


# ---------------------------------------------------------------------------
# _fetch_unseen_emails
# ---------------------------------------------------------------------------


class TestFetchUnseenEmails:
    """Test _fetch_unseen_emails retrieves and decodes raw emails."""

    def _build_raw_email(self, sender="a@b.com", subject="Test") -> str:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = "lab@test.com"
        msg["Subject"] = subject
        msg.attach(MIMEText("Body text", "plain"))
        return msg.as_string()

    def test_fetches_single_email(self):
        """Fetches one unseen email and returns its raw string."""
        raw = self._build_raw_email()
        conn = MagicMock()
        conn.search.return_value = ("OK", [b"1"])
        conn.fetch.return_value = ("OK", [(b"1 (RFC822 {500})", raw.encode("utf-8"))])

        result = _fetch_unseen_emails(conn, "INBOX")

        conn.select.assert_called_once_with("INBOX")
        conn.search.assert_called_once_with(None, "UNSEEN")
        assert len(result) == 1
        assert "From: a@b.com" in result[0]

    def test_fetches_multiple_emails(self):
        """Fetches multiple unseen emails."""
        raw1 = self._build_raw_email(subject="Sub1")
        raw2 = self._build_raw_email(subject="Sub2")

        conn = MagicMock()
        conn.search.return_value = ("OK", [b"1 2"])

        def mock_fetch(num, parts):
            idx = int(num) - 1
            data = [raw1, raw2][idx].encode("utf-8")
            return ("OK", [(num + b" (RFC822 {500})", data)])

        conn.fetch.side_effect = mock_fetch

        result = _fetch_unseen_emails(conn, "INBOX")
        assert len(result) == 2

    def test_no_unseen_emails(self):
        """Returns empty list when no unseen emails."""
        conn = MagicMock()
        conn.search.return_value = ("OK", [b""])

        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []
        conn.fetch.assert_not_called()

    def test_skips_empty_message_number(self):
        """Skips empty byte strings in message number list."""
        conn = MagicMock()
        # Simulate edge case where split produces empty strings
        conn.search.return_value = ("OK", [b""])
        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_handles_none_data_gracefully(self):
        """Skips when fetch returns None data."""
        conn = MagicMock()
        conn.search.return_value = ("OK", [b"1"])
        conn.fetch.return_value = ("OK", [None])

        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_handles_non_tuple_data_gracefully(self):
        """Skips when fetch returns non-tuple data element."""
        conn = MagicMock()
        conn.search.return_value = ("OK", [b"1"])
        conn.fetch.return_value = ("OK", [b"just-bytes-not-tuple"])

        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_handles_non_bytes_payload_gracefully(self):
        """Skips when the RFC822 payload is not bytes."""
        conn = MagicMock()
        conn.search.return_value = ("OK", [b"1"])
        conn.fetch.return_value = ("OK", [(b"1 (RFC822)", "string-not-bytes")])

        result = _fetch_unseen_emails(conn, "INBOX")
        assert result == []

    def test_decodes_utf8_with_replace(self):
        """Decodes bytes with errors='replace' for non-utf8 content."""
        raw_bytes = b"Subject: Test\n\nHello \xff invalid"
        conn = MagicMock()
        conn.search.return_value = ("OK", [b"1"])
        conn.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", raw_bytes)])

        result = _fetch_unseen_emails(conn, "INBOX")
        assert len(result) == 1
        # The replacement character should appear instead of raising
        assert "\ufffd" in result[0] or "Hello" in result[0]


# ---------------------------------------------------------------------------
# poll_once
# ---------------------------------------------------------------------------


class TestPollOnce:
    """Test poll_once single poll cycle."""

    def test_returns_zero_when_host_missing(self, monkeypatch):
        """Returns 0 when EMAIL_IMAP_HOST is not set."""
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        assert poll_once() == 0

    def test_returns_zero_when_user_missing(self, monkeypatch):
        """Returns 0 when EMAIL_IMAP_USER is not set."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        assert poll_once() == 0

    def test_returns_zero_when_password_missing(self, monkeypatch):
        """Returns 0 when EMAIL_IMAP_PASSWORD is not set."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        assert poll_once() == 0

    def test_returns_zero_when_all_missing(self):
        """Returns 0 when all IMAP env vars are unset."""
        assert poll_once() == 0

    @patch("lab_manager.services.email_poller._connect_imap")
    def test_imap_connection_failure_returns_zero(self, mock_connect, monkeypatch):
        """Returns 0 when IMAP connection fails."""
        mock_connect.side_effect = Exception("Connection refused")
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        assert poll_once() == 0

    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.services.email_poller._connect_imap")
    def test_processes_emails_and_returns_doc_count(
        self, mock_connect, mock_fetch, mock_db, monkeypatch
    ):
        """Processes fetched emails and returns total document count."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = ["raw-email-1", "raw-email-2"]

        @contextmanager
        def fake_session():
            yield MagicMock()

        mock_db.side_effect = fake_session

        with patch("lab_manager.services.email_intake.process_email") as mock_process:
            mock_process.return_value = ["doc1"]
            result = poll_once()

        assert result == 2
        mock_conn.logout.assert_called_once()

    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.services.email_poller._connect_imap")
    def test_single_email_multiple_docs(
        self, mock_connect, mock_fetch, mock_db, monkeypatch
    ):
        """One email producing multiple docs counts all of them."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = ["raw-email"]

        @contextmanager
        def fake_session():
            yield MagicMock()

        mock_db.side_effect = fake_session

        with patch("lab_manager.services.email_intake.process_email") as mock_process:
            mock_process.return_value = ["doc1", "doc2", "doc3"]
            result = poll_once()

        assert result == 3

    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.services.email_poller._connect_imap")
    def test_no_unseen_emails_returns_zero(
        self, mock_connect, mock_fetch, mock_db, monkeypatch
    ):
        """Returns 0 when no unseen emails in mailbox."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = []

        result = poll_once()

        assert result == 0
        mock_conn.logout.assert_called_once()

    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.services.email_poller._connect_imap")
    def test_email_processing_failure_continues(
        self, mock_connect, mock_fetch, mock_db, monkeypatch
    ):
        """Continues processing when one email fails."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = ["bad-email", "good-email"]

        @contextmanager
        def fake_session():
            yield MagicMock()

        mock_db.side_effect = fake_session

        with patch("lab_manager.services.email_intake.process_email") as mock_process:
            mock_process.side_effect = [Exception("parse error"), ["doc1"]]
            result = poll_once()

        assert result == 1

    @patch("lab_manager.database.get_db_session")
    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.services.email_poller._connect_imap")
    def test_logout_failure_suppressed(
        self, mock_connect, mock_fetch, mock_db, monkeypatch
    ):
        """Logout failure does not propagate."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        mock_conn = MagicMock()
        mock_conn.logout.side_effect = Exception("already closed")
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = []

        # Should not raise
        result = poll_once()
        assert result == 0

    @patch("lab_manager.services.email_poller._fetch_unseen_emails")
    @patch("lab_manager.services.email_poller._connect_imap")
    def test_select_folder_from_config(self, mock_connect, mock_fetch, monkeypatch):
        """Uses EMAIL_FOLDER from config when fetching."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        monkeypatch.setenv("EMAIL_FOLDER", "VendorEmails")

        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        mock_fetch.return_value = []

        poll_once()

        mock_fetch.assert_called_once_with(mock_conn, "VendorEmails")


# ---------------------------------------------------------------------------
# run_poller
# ---------------------------------------------------------------------------


class TestRunPoller:
    """Test run_poller loop behavior."""

    def test_returns_immediately_when_host_missing(self, monkeypatch):
        """Returns immediately when EMAIL_IMAP_HOST not configured."""
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        # Should not block
        run_poller()

    def test_returns_immediately_when_user_missing(self, monkeypatch):
        """Returns immediately when EMAIL_IMAP_USER not configured."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        run_poller()

    def test_returns_immediately_when_password_missing(self, monkeypatch):
        """Returns immediately when EMAIL_IMAP_PASSWORD not configured."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        run_poller()

    @patch("lab_manager.services.email_poller.time.sleep")
    @patch("lab_manager.services.email_poller.poll_once")
    def test_loops_with_configured_interval(
        self, mock_poll_once, mock_sleep, monkeypatch
    ):
        """Loops calling poll_once and sleeping for configured interval."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "10")

        # Stop after 3 iterations
        call_count = 0

        def stop_after_3(_interval):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                raise KeyboardInterrupt

        mock_poll_once.return_value = 0
        mock_sleep.side_effect = stop_after_3

        with pytest.raises(KeyboardInterrupt):
            run_poller()

        assert mock_poll_once.call_count == 3
        mock_sleep.assert_called_with(10)

    @patch("lab_manager.services.email_poller.time.sleep")
    @patch("lab_manager.services.email_poller.poll_once")
    def test_continues_after_poll_exception(
        self, mock_poll_once, mock_sleep, monkeypatch
    ):
        """Continues looping even when poll_once raises an exception."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")
        monkeypatch.setenv("EMAIL_POLL_INTERVAL", "5")

        iteration = 0

        def stop_after_3_sleeps(_interval):
            nonlocal iteration
            iteration += 1
            if iteration >= 3:
                raise KeyboardInterrupt

        # First poll raises, second succeeds
        mock_poll_once.side_effect = [Exception("transient failure"), 5]
        mock_sleep.side_effect = stop_after_3_sleeps

        with pytest.raises(KeyboardInterrupt):
            run_poller()

        # Should have called poll_once at least twice (exception + success)
        assert mock_poll_once.call_count >= 2

    @patch("lab_manager.services.email_poller.time.sleep")
    @patch("lab_manager.services.email_poller.poll_once")
    def test_uses_default_interval_when_not_set(
        self, mock_poll_once, mock_sleep, monkeypatch
    ):
        """Uses DEFAULT_POLL_INTERVAL when EMAIL_POLL_INTERVAL not set."""
        monkeypatch.setenv("EMAIL_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("EMAIL_IMAP_USER", "lab@test.com")
        monkeypatch.setenv("EMAIL_IMAP_PASSWORD", "pass")

        mock_poll_once.return_value = 0
        mock_sleep.side_effect = [KeyboardInterrupt]

        with pytest.raises(KeyboardInterrupt):
            run_poller()

        mock_sleep.assert_called_once_with(DEFAULT_POLL_INTERVAL)
