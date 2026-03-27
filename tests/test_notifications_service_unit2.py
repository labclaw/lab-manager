"""Unit tests for lab_manager.services.notifications — fully mocked HTTP and channels."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from lab_manager.services.notifications import (
    LogChannel,
    NotificationChannel,
    NotificationDispatcher,
    SlackChannel,
    WebhookChannel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(
    severity: str = "info",
    alert_type: str = "test_alert",
    message: str = "Something happened",
    entity_type: str = "inventory",
    entity_id: int = 1,
) -> dict:
    """Build a minimal alert dict for testing."""
    return {
        "severity": severity,
        "type": alert_type,
        "message": message,
        "entity_type": entity_type,
        "entity_id": entity_id,
    }


def _mock_httpx_post_success(status_code: int = 200):
    """Return a mock httpx.post that returns a successful response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _mock_httpx_post_failure(status_code: int = 500):
    """Return a mock httpx.post that raises HTTPStatusError."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=MagicMock(),
        response=resp,
    )
    return resp


def _mock_httpx_post_exception(exc: Exception):
    """Return a mock httpx.post that raises an arbitrary exception."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = exc
    return mock_resp


# ===================================================================
# NotificationChannel (base class) — format_message
# ===================================================================


class TestNotificationChannelFormatMessage:
    """Tests for NotificationChannel.format_message (tested via concrete subclass)."""

    def _channel(self):
        return LogChannel()

    def test_basic_formatting(self):
        ch = self._channel()
        alert = _make_alert(
            severity="critical", alert_type="expired", message="Lot expired"
        )
        result = ch.format_message(alert)
        assert "[CRITICAL]" in result
        assert "expired" in result
        assert "Lot expired" in result

    def test_warning_severity_uppercase(self):
        ch = self._channel()
        alert = _make_alert(severity="warning")
        result = ch.format_message(alert)
        assert "[WARNING]" in result

    def test_info_severity_uppercase(self):
        ch = self._channel()
        alert = _make_alert(severity="info")
        result = ch.format_message(alert)
        assert "[INFO]" in result

    def test_default_severity_is_info(self):
        ch = self._channel()
        alert = {"type": "test", "message": "msg"}
        result = ch.format_message(alert)
        assert "[INFO]" in result

    def test_default_type_is_unknown(self):
        ch = self._channel()
        alert = {"severity": "info", "message": "msg"}
        result = ch.format_message(alert)
        assert "unknown" in result

    def test_default_message_is_empty(self):
        ch = self._channel()
        alert = {"severity": "info", "type": "test"}
        result = ch.format_message(alert)
        # The message portion after the em dash should be present
        assert " — " in result

    def test_entity_formatting(self):
        ch = self._channel()
        alert = _make_alert(entity_type="product", entity_id=42)
        result = ch.format_message(alert)
        assert "product#42" in result

    def test_default_entity_type_is_question_mark(self):
        ch = self._channel()
        alert = {"severity": "info", "type": "test", "message": "msg"}
        result = ch.format_message(alert)
        assert "?#?" in result

    def test_custom_severity_not_uppercase_mapped(self):
        """Unknown severity should still be uppercased."""
        ch = self._channel()
        alert = _make_alert(severity="debug")
        result = ch.format_message(alert)
        assert "[DEBUG]" in result

    def test_full_format_string(self):
        ch = self._channel()
        alert = _make_alert(
            severity="critical",
            alert_type="expired",
            message="Item LOT-1 expired",
            entity_type="inventory",
            entity_id=5,
        )
        result = ch.format_message(alert)
        assert result == "[CRITICAL] expired — Item LOT-1 expired (inventory#5)"


# ===================================================================
# SlackChannel
# ===================================================================


class TestSlackChannelInit:
    """Tests for SlackChannel initialization."""

    def test_default_name(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        assert ch.name == "slack"

    def test_default_username(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        assert ch.username == "Lab Manager"

    def test_default_timeout(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        assert ch.timeout == 10.0

    def test_default_channel_empty(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        assert ch.channel == ""

    def test_custom_username(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test", username="Bot")
        assert ch.username == "Bot"

    def test_custom_channel_override(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test", channel="#alerts")
        assert ch.channel == "#alerts"

    def test_custom_timeout(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test", timeout=5.0)
        assert ch.timeout == 5.0


class TestSlackChannelSend:
    """Tests for SlackChannel.send."""

    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_critical_alert(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert(severity="critical")
        result = ch.send(alert)
        assert result is True
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]
        assert ":red_circle:" in payload["text"]
        assert payload["username"] == "Lab Manager"

    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_warning_alert(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert(severity="warning")
        result = ch.send(alert)
        assert result is True
        payload = mock_post.call_args.kwargs["json"]
        assert ":warning:" in payload["text"]

    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_info_alert(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert(severity="info")
        result = ch.send(alert)
        assert result is True
        payload = mock_post.call_args.kwargs["json"]
        assert ":information_source:" in payload["text"]

    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_unknown_severity_emoji(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert(severity="debug")
        result = ch.send(alert)
        assert result is True
        payload = mock_post.call_args.kwargs["json"]
        assert ":grey_question:" in payload["text"]

    @patch("lab_manager.services.notifications.httpx.post")
    def test_channel_override_in_payload(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(
            webhook_url="https://hooks.slack.com/test", channel="#custom-alerts"
        )
        alert = _make_alert()
        ch.send(alert)
        payload = mock_post.call_args.kwargs["json"]
        assert payload["channel"] == "#custom-alerts"

    @patch("lab_manager.services.notifications.httpx.post")
    def test_no_channel_key_when_empty(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()
        ch.send(alert)
        payload = mock_post.call_args.kwargs["json"]
        assert "channel" not in payload

    @patch("lab_manager.services.notifications.httpx.post")
    def test_custom_username_in_payload(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(
            webhook_url="https://hooks.slack.com/test", username="AlertBot"
        )
        alert = _make_alert()
        ch.send(alert)
        payload = mock_post.call_args.kwargs["json"]
        assert payload["username"] == "AlertBot"

    @patch("lab_manager.services.notifications.httpx.post")
    def test_webhook_url_used(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        url = "https://hooks.slack.com/T/B/xxx"
        ch = SlackChannel(webhook_url=url)
        alert = _make_alert()
        ch.send(alert)
        assert mock_post.call_args.args[0] == url

    @patch("lab_manager.services.notifications.httpx.post")
    def test_timeout_used(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test", timeout=3.0)
        alert = _make_alert()
        ch.send(alert)
        assert mock_post.call_args.kwargs["timeout"] == 3.0

    @patch("lab_manager.services.notifications.httpx.post")
    def test_http_error_returns_false(self, mock_post):
        mock_post.return_value = _mock_httpx_post_failure(500)
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_connection_error_returns_false(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_timeout_error_returns_false(self, mock_post):
        mock_post.side_effect = httpx.TimeoutException("Timed out")
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_generic_exception_returns_false(self, mock_post):
        mock_post.side_effect = RuntimeError("Unexpected error")
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False


# ===================================================================
# WebhookChannel
# ===================================================================


class TestWebhookChannelInit:
    """Tests for WebhookChannel initialization."""

    def test_default_name(self):
        ch = WebhookChannel(url="https://example.com/hook")
        assert ch.name == "webhook"

    def test_default_headers_empty(self):
        ch = WebhookChannel(url="https://example.com/hook")
        assert ch.headers == {}

    def test_default_timeout(self):
        ch = WebhookChannel(url="https://example.com/hook")
        assert ch.timeout == 10.0

    def test_custom_headers(self):
        ch = WebhookChannel(
            url="https://example.com/hook",
            headers={"Authorization": "Bearer token123"},
        )
        assert ch.headers == {"Authorization": "Bearer token123"}

    def test_custom_timeout(self):
        ch = WebhookChannel(url="https://example.com/hook", timeout=5.0)
        assert ch.timeout == 5.0


class TestWebhookChannelSend:
    """Tests for WebhookChannel.send."""

    @patch("lab_manager.services.notifications.httpx.post")
    def test_successful_send(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is True

    @patch("lab_manager.services.notifications.httpx.post")
    def test_sends_alert_as_json_body(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert(severity="critical", alert_type="expired")
        ch.send(alert)
        call_kwargs = mock_post.call_args.kwargs
        body = json.loads(call_kwargs["content"])
        assert body["severity"] == "critical"
        assert body["type"] == "expired"

    @patch("lab_manager.services.notifications.httpx.post")
    def test_content_type_header_set(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert()
        ch.send(alert)
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Content-Type"] == "application/json"

    @patch("lab_manager.services.notifications.httpx.post")
    def test_custom_headers_merged(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(
            url="https://example.com/hook",
            headers={"X-Custom": "value", "Authorization": "Bearer x"},
        )
        alert = _make_alert()
        ch.send(alert)
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-Custom"] == "value"
        assert headers["Authorization"] == "Bearer x"
        assert headers["Content-Type"] == "application/json"

    @patch("lab_manager.services.notifications.httpx.post")
    def test_url_used(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        url = "https://my.server.com/webhook/alerts"
        ch = WebhookChannel(url=url)
        alert = _make_alert()
        ch.send(alert)
        assert mock_post.call_args.args[0] == url

    @patch("lab_manager.services.notifications.httpx.post")
    def test_timeout_used(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(url="https://example.com/hook", timeout=2.5)
        alert = _make_alert()
        ch.send(alert)
        assert mock_post.call_args.kwargs["timeout"] == 2.5

    @patch("lab_manager.services.notifications.httpx.post")
    def test_http_error_returns_false(self, mock_post):
        mock_post.return_value = _mock_httpx_post_failure(503)
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_connection_error_returns_false(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_timeout_error_returns_false(self, mock_post):
        mock_post.side_effect = httpx.TimeoutException("Timed out")
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_generic_exception_returns_false(self, mock_post):
        mock_post.side_effect = ValueError("bad value")
        ch = WebhookChannel(url="https://example.com/hook")
        alert = _make_alert()
        result = ch.send(alert)
        assert result is False

    @patch("lab_manager.services.notifications.httpx.post")
    def test_non_serializable_fields_use_str(self, mock_post):
        """Alert fields that are not JSON-serializable should be converted via default=str."""
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(url="https://example.com/hook")
        alert = {"severity": "info", "type": "test", "data": set([1, 2, 3])}
        ch.send(alert)
        # Should not raise; default=str handles non-serializable types
        body_str = mock_post.call_args.kwargs["content"]
        assert isinstance(body_str, str)

    @patch("lab_manager.services.notifications.httpx.post")
    def test_empty_alert_dict(self, mock_post):
        mock_post.return_value = _mock_httpx_post_success()
        ch = WebhookChannel(url="https://example.com/hook")
        result = ch.send({})
        assert result is True


# ===================================================================
# LogChannel
# ===================================================================


class TestLogChannelInit:
    """Tests for LogChannel initialization."""

    def test_default_name(self):
        ch = LogChannel()
        assert ch.name == "log"

    def test_default_logger_name(self):
        ch = LogChannel()
        assert ch.logger_name == "lab_manager.alerts.notifications"

    def test_custom_logger_name(self):
        ch = LogChannel(logger_name="custom.logger")
        assert ch.logger_name == "custom.logger"


class TestLogChannelSend:
    """Tests for LogChannel.send."""

    def test_always_returns_true(self):
        ch = LogChannel()
        alert = _make_alert()
        assert ch.send(alert) is True

    def test_critical_logs_at_critical_level(self, caplog):
        ch = LogChannel()
        alert = _make_alert(severity="critical")
        with caplog.at_level(
            logging.CRITICAL, logger="lab_manager.alerts.notifications"
        ):
            ch.send(alert)
        assert any("[CRITICAL]" in r.message for r in caplog.records)

    def test_warning_logs_at_warning_level(self, caplog):
        ch = LogChannel()
        alert = _make_alert(severity="warning")
        with caplog.at_level(
            logging.WARNING, logger="lab_manager.alerts.notifications"
        ):
            ch.send(alert)
        assert any("[WARNING]" in r.message for r in caplog.records)

    def test_info_logs_at_info_level(self, caplog):
        ch = LogChannel()
        alert = _make_alert(severity="info")
        with caplog.at_level(logging.INFO, logger="lab_manager.alerts.notifications"):
            ch.send(alert)
        assert any("[INFO]" in r.message for r in caplog.records)

    def test_unknown_severity_logs_at_info_level(self, caplog):
        ch = LogChannel()
        alert = _make_alert(severity="unknown_level")
        with caplog.at_level(logging.INFO, logger="lab_manager.alerts.notifications"):
            ch.send(alert)
        assert any("[UNKNOWN_LEVEL]" in r.message for r in caplog.records)

    def test_empty_alert_returns_true(self):
        ch = LogChannel()
        assert ch.send({}) is True

    def test_custom_logger_name_used(self, caplog):
        ch = LogChannel(logger_name="test.custom.logger")
        alert = _make_alert()
        with caplog.at_level(logging.INFO, logger="test.custom.logger"):
            ch.send(alert)
        assert any("test_alert" in r.message for r in caplog.records)


# ===================================================================
# NotificationDispatcher — add_channel
# ===================================================================


class TestNotificationDispatcherAddChannel:
    """Tests for NotificationDispatcher.add_channel."""

    def test_add_single_channel(self):
        d = NotificationDispatcher()
        ch = LogChannel()
        d.add_channel(ch)
        assert d.channels == ["log"]

    def test_add_multiple_channels(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel())
        d.add_channel(SlackChannel(webhook_url="https://hooks.slack.com/test"))
        assert d.channels == ["log", "slack"]

    def test_add_channel_with_custom_severities(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical"})
        # Channel should be registered; only critical alerts will route to it
        assert d.channels == ["log"]

    def test_add_channel_with_no_severities_defaults_to_all(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities=None)
        # Default severities = {critical, warning, info}
        alert_critical = _make_alert(severity="critical")
        alert_warning = _make_alert(severity="warning")
        alert_info = _make_alert(severity="info")

        r1 = d.notify(alert_critical)
        r2 = d.notify(alert_warning)
        r3 = d.notify(alert_info)
        assert "log" in r1
        assert "log" in r2
        assert "log" in r3

    def test_add_same_channel_type_twice(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(logger_name="logger1"))
        d.add_channel(LogChannel(logger_name="logger2"))
        # Both registered, names may collide but are separate instances
        assert len(d.channels) == 2


# ===================================================================
# NotificationDispatcher — channels property
# ===================================================================


class TestNotificationDispatcherChannelsProperty:
    """Tests for NotificationDispatcher.channels property."""

    def test_empty_when_no_channels(self):
        d = NotificationDispatcher()
        assert d.channels == []

    def test_returns_channel_names(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel())
        d.add_channel(SlackChannel(webhook_url="https://hooks.slack.com/test"))
        d.add_channel(WebhookChannel(url="https://example.com/hook"))
        assert d.channels == ["log", "slack", "webhook"]


# ===================================================================
# NotificationDispatcher — notify
# ===================================================================


class TestNotificationDispatcherNotify:
    """Tests for NotificationDispatcher.notify."""

    def test_no_channels_returns_empty_dict(self):
        d = NotificationDispatcher()
        result = d.notify(_make_alert())
        assert result == {}

    def test_single_matching_channel(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel())
        result = d.notify(_make_alert(severity="info"))
        assert "log" in result
        assert result["log"] is True

    def test_severity_filter_blocks_non_matching(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical"})
        result = d.notify(_make_alert(severity="info"))
        assert "log" not in result

    def test_severity_filter_allows_matching(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical"})
        result = d.notify(_make_alert(severity="critical"))
        assert "log" in result
        assert result["log"] is True

    def test_multiple_channels_with_different_severities(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical", "warning"})
        d.add_channel(
            SlackChannel(webhook_url="https://hooks.slack.com/test"),
            severities={"critical"},
        )
        result = d.notify(_make_alert(severity="warning"))
        assert "log" in result
        assert "slack" not in result

    def test_critical_alert_reaches_critical_only_channels(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical"})
        d.add_channel(
            SlackChannel(webhook_url="https://hooks.slack.com/test"),
            severities={"info"},
        )
        result = d.notify(_make_alert(severity="critical"))
        assert "log" in result
        assert "slack" not in result

    def test_default_severity_is_info(self):
        """Alert with no severity key defaults to 'info'."""
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"info"})
        result = d.notify({"type": "test", "message": "msg"})
        assert "log" in result

    @patch("lab_manager.services.notifications.httpx.post")
    def test_returns_false_on_send_failure(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        d = NotificationDispatcher()
        d.add_channel(SlackChannel(webhook_url="https://hooks.slack.com/test"))
        result = d.notify(_make_alert(severity="info"))
        assert result["slack"] is False

    def test_all_severities_match_all_channels(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel())
        for severity in ("critical", "warning", "info"):
            result = d.notify(_make_alert(severity=severity))
            assert "log" in result
            assert result["log"] is True


# ===================================================================
# NotificationDispatcher — notify_batch
# ===================================================================


class TestNotificationDispatcherNotifyBatch:
    """Tests for NotificationDispatcher.notify_batch."""

    def test_empty_batch_returns_empty_dict(self):
        d = NotificationDispatcher()
        result = d.notify_batch([])
        assert result == {}

    def test_single_alert_single_channel(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel())
        alerts = [_make_alert(severity="info")]
        result = d.notify_batch(alerts)
        assert result["log"] == 1

    def test_multiple_alerts_counted(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel())
        alerts = [
            _make_alert(severity="info"),
            _make_alert(severity="warning"),
            _make_alert(severity="critical"),
        ]
        result = d.notify_batch(alerts)
        assert result["log"] == 3

    def test_severity_filter_affects_batch_count(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical"})
        alerts = [
            _make_alert(severity="info"),
            _make_alert(severity="critical"),
            _make_alert(severity="warning"),
            _make_alert(severity="critical"),
        ]
        result = d.notify_batch(alerts)
        assert result["log"] == 2

    @patch("lab_manager.services.notifications.httpx.post")
    def test_failed_sends_not_counted(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        d = NotificationDispatcher()
        d.add_channel(SlackChannel(webhook_url="https://hooks.slack.com/test"))
        alerts = [_make_alert(severity="info")]
        result = d.notify_batch(alerts)
        # Failed sends should not appear in counts
        assert "slack" not in result

    def test_multiple_channels_independent_counts(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical", "warning"})
        d.add_channel(LogChannel(logger_name="logger2"), severities={"info"})
        alerts = [
            _make_alert(severity="critical"),
            _make_alert(severity="info"),
            _make_alert(severity="info"),
        ]
        result = d.notify_batch(alerts)
        # Both channels share name "log", so counts merge
        assert "log" in result

    def test_batch_with_no_matching_alerts(self):
        d = NotificationDispatcher()
        d.add_channel(LogChannel(), severities={"critical"})
        alerts = [_make_alert(severity="info"), _make_alert(severity="warning")]
        result = d.notify_batch(alerts)
        assert result == {}


# ===================================================================
# NotificationChannel ABC — cannot be instantiated directly
# ===================================================================


class TestNotificationChannelABC:
    """Tests for NotificationChannel abstract base class."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            NotificationChannel()

    def test_subclass_must_implement_send(self):
        class IncompleteChannel(NotificationChannel):
            pass

        with pytest.raises(TypeError):
            IncompleteChannel()

    def test_subclass_with_send_works(self):
        class MinimalChannel(NotificationChannel):
            name = "minimal"

            def send(self, alert):
                return True

        ch = MinimalChannel()
        assert ch.send({}) is True

    def test_format_message_inherited(self):
        class MinimalChannel(NotificationChannel):
            name = "minimal"

            def send(self, alert):
                return True

        ch = MinimalChannel()
        result = ch.format_message(
            {"severity": "info", "type": "test", "message": "hello"}
        )
        assert "[INFO]" in result
        assert "test" in result
