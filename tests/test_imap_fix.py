"""Test that _connect_imap uses the password parameter, not env re-read."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lab_manager.services.email_poller import _connect_imap


@patch("lab_manager.services.email_poller.imaplib.IMAP4_SSL")
def test_connect_imap_uses_param_password(mock_imap_cls):
    """_connect_imap must use the password arg, not re-read from env."""
    mock_conn = MagicMock()
    mock_imap_cls.return_value = mock_conn

    config = {"host": "imap.example.com", "user": "user@example.com"}
    _connect_imap(config, "correct-password")

    mock_conn.login.assert_called_once_with("user@example.com", "correct-password")
