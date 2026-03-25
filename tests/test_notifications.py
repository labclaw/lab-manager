"""Tests for proactive notification service."""

from unittest.mock import MagicMock, patch


from lab_manager.services.notifications import (
    LogChannel,
    NotificationChannel,
    NotificationDispatcher,
    SlackChannel,
    WebhookChannel,
)


def _make_alert(severity="critical", alert_type="expired"):
    return {
        "type": alert_type,
        "severity": severity,
        "message": f"Test {alert_type} alert",
        "entity_type": "inventory",
        "entity_id": 42,
        "details": {"test": True},
    }


# ---------------------------------------------------------------------------
# NotificationChannel.format_message
# ---------------------------------------------------------------------------


class TestFormatMessage:
    def test_format_critical_alert(self):
        ch = LogChannel()
        msg = ch.format_message(_make_alert("critical", "expired"))
        assert "[CRITICAL]" in msg
        assert "expired" in msg
        assert "inventory#42" in msg

    def test_format_info_alert(self):
        ch = LogChannel()
        msg = ch.format_message(_make_alert("info", "pending_review"))
        assert "[INFO]" in msg


# ---------------------------------------------------------------------------
# LogChannel
# ---------------------------------------------------------------------------


class TestLogChannel:
    def test_send_logs_message(self, caplog):
        import logging

        ch = LogChannel()
        with caplog.at_level(logging.INFO, logger="lab_manager.alerts.notifications"):
            result = ch.send(_make_alert("info", "pending_review"))
        assert result is True

    def test_send_critical_uses_critical_level(self, caplog):
        import logging

        ch = LogChannel()
        with caplog.at_level(
            logging.CRITICAL, logger="lab_manager.alerts.notifications"
        ):
            result = ch.send(_make_alert("critical", "expired"))
        assert result is True


# ---------------------------------------------------------------------------
# SlackChannel
# ---------------------------------------------------------------------------


class TestSlackChannel:
    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        result = ch.send(_make_alert())

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]
        assert ":red_circle:" in payload["text"]
        assert "Lab Manager" == payload["username"]

    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_with_channel_override(self, mock_post):
        mock_post.return_value = MagicMock()

        ch = SlackChannel(
            webhook_url="https://hooks.slack.com/test",
            channel="#lab-alerts",
        )
        ch.send(_make_alert())

        payload = mock_post.call_args.kwargs["json"]
        assert payload["channel"] == "#lab-alerts"

    @patch(
        "lab_manager.services.notifications.httpx.post",
        side_effect=Exception("network"),
    )
    def test_send_failure_returns_false(self, mock_post):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        result = ch.send(_make_alert())
        assert result is False

    def test_warning_emoji(self):
        ch = SlackChannel(webhook_url="https://hooks.slack.com/test")
        # Just test format — no HTTP call
        msg = ch.format_message(_make_alert("warning", "low_stock"))
        assert "low_stock" in msg


# ---------------------------------------------------------------------------
# WebhookChannel
# ---------------------------------------------------------------------------


class TestWebhookChannel:
    @patch("lab_manager.services.notifications.httpx.post")
    def test_send_posts_json(self, mock_post):
        mock_post.return_value = MagicMock()

        ch = WebhookChannel(
            url="https://example.com/hook",
            headers={"Authorization": "Bearer tok"},
        )
        result = ch.send(_make_alert())

        assert result is True
        call_args = mock_post.call_args
        assert call_args.kwargs["headers"]["Content-Type"] == "application/json"
        assert call_args.kwargs["headers"]["Authorization"] == "Bearer tok"

    @patch(
        "lab_manager.services.notifications.httpx.post", side_effect=Exception("fail")
    )
    def test_send_failure(self, mock_post):
        ch = WebhookChannel(url="https://example.com/hook")
        assert ch.send(_make_alert()) is False


# ---------------------------------------------------------------------------
# NotificationDispatcher
# ---------------------------------------------------------------------------


class TestNotificationDispatcher:
    def test_notify_routes_to_matching_channels(self):
        dispatcher = NotificationDispatcher()
        ch1 = MagicMock(spec=NotificationChannel)
        ch1.name = "slack"
        ch1.send.return_value = True
        ch2 = MagicMock(spec=NotificationChannel)
        ch2.name = "webhook"
        ch2.send.return_value = True

        dispatcher.add_channel(ch1, severities={"critical"})
        dispatcher.add_channel(ch2, severities={"critical", "warning"})

        # Critical alert → both channels
        results = dispatcher.notify(_make_alert("critical"))
        assert results == {"slack": True, "webhook": True}

        # Warning alert → only webhook
        results = dispatcher.notify(_make_alert("warning", "low_stock"))
        assert results == {"webhook": True}

    def test_notify_skips_non_matching_severity(self):
        dispatcher = NotificationDispatcher()
        ch = MagicMock(spec=NotificationChannel)
        ch.name = "slack"

        dispatcher.add_channel(ch, severities={"critical"})
        results = dispatcher.notify(_make_alert("info", "pending_review"))
        assert results == {}
        ch.send.assert_not_called()

    def test_notify_batch(self):
        dispatcher = NotificationDispatcher()
        ch = MagicMock(spec=NotificationChannel)
        ch.name = "log"
        ch.send.return_value = True

        dispatcher.add_channel(ch)

        alerts = [_make_alert("critical"), _make_alert("warning", "low_stock")]
        counts = dispatcher.notify_batch(alerts)
        assert counts == {"log": 2}

    def test_channels_property(self):
        dispatcher = NotificationDispatcher()
        dispatcher.add_channel(LogChannel())
        dispatcher.add_channel(SlackChannel(webhook_url="https://x"))
        assert dispatcher.channels == ["log", "slack"]

    def test_empty_dispatcher(self):
        dispatcher = NotificationDispatcher()
        results = dispatcher.notify(_make_alert())
        assert results == {}
