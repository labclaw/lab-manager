"""Proactive alert notification service.

Inspired by OpenClaw's multi-channel Gateway pattern: instead of requiring
users to poll ``GET /alerts``, push critical alerts to configured channels
(Slack webhook, generic HTTP webhook, or email placeholder).

Usage::

    from lab_manager.services.notifications import NotificationDispatcher, SlackChannel

    dispatcher = NotificationDispatcher()
    dispatcher.add_channel(SlackChannel(webhook_url="https://hooks.slack.com/..."))
    dispatcher.notify(alert_dict)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from lab_manager.config import get_settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Channel abstraction
# ---------------------------------------------------------------------------


class NotificationChannel(ABC):
    """Base class for notification channels."""

    name: str = "base"

    @abstractmethod
    def send(self, alert: dict[str, Any]) -> bool:
        """Send an alert notification.  Return True on success."""
        ...

    def format_message(self, alert: dict[str, Any]) -> str:
        """Format alert dict into a human-readable message."""
        severity = alert.get("severity", "info").upper()
        alert_type = alert.get("type", "unknown")
        message = alert.get("message", "")
        entity = f"{alert.get('entity_type', '?')}#{alert.get('entity_id', '?')}"
        return f"[{severity}] {alert_type} — {message} ({entity})"


@dataclass
class SlackChannel(NotificationChannel):
    """Send alerts to a Slack incoming webhook."""

    name: str = "slack"
    webhook_url: str = ""
    channel: str = ""  # override channel (optional)
    username: str = "Lab Manager"
    timeout: float = 10.0

    def send(self, alert: dict[str, Any]) -> bool:
        severity = alert.get("severity", "info")
        emoji = {
            "critical": ":red_circle:",
            "warning": ":warning:",
            "info": ":information_source:",
        }.get(severity, ":grey_question:")
        text = self.format_message(alert)

        payload: dict[str, Any] = {
            "text": f"{emoji} {text}",
            "username": self.username,
        }
        if self.channel:
            payload["channel"] = self.channel

        try:
            resp = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except Exception:
            log.exception("Slack notification failed for alert: %s", alert.get("type"))
            return False


@dataclass
class WebhookChannel(NotificationChannel):
    """Send alerts as JSON POST to a generic HTTP endpoint."""

    name: str = "webhook"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 10.0

    def send(self, alert: dict[str, Any]) -> bool:
        try:
            resp = httpx.post(
                self.url,
                content=json.dumps(alert, default=str),
                headers={"Content-Type": "application/json", **self.headers},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return True
        except Exception:
            log.exception(
                "Webhook notification failed for alert: %s", alert.get("type")
            )
            return False


@dataclass
class LogChannel(NotificationChannel):
    """Log alerts to Python logger (useful for dev / as fallback)."""

    name: str = "log"
    logger_name: str = "lab_manager.alerts.notifications"

    def send(self, alert: dict[str, Any]) -> bool:
        logger = logging.getLogger(self.logger_name)
        severity = alert.get("severity", "info")
        level = {
            "critical": logging.CRITICAL,
            "warning": logging.WARNING,
            "info": logging.INFO,
        }.get(severity, logging.INFO)
        logger.log(level, self.format_message(alert))
        return True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class NotificationDispatcher:
    """Route alerts to configured notification channels.

    Supports severity-based filtering per channel and batch dispatch.
    """

    def __init__(self) -> None:
        self._channels: list[tuple[NotificationChannel, set[str]]] = []

    def add_channel(
        self,
        channel: NotificationChannel,
        severities: set[str] | None = None,
    ) -> None:
        """Register a notification channel.

        Parameters
        ----------
        channel : NotificationChannel
            The channel to add.
        severities : set[str], optional
            Only send alerts matching these severities.
            Defaults to all severities (critical, warning, info).
        """
        allowed = severities or {"critical", "warning", "info"}
        self._channels.append((channel, allowed))
        log.info(
            "Registered notification channel: %s (severities=%s)",
            channel.name,
            allowed,
        )

    def notify(self, alert: dict[str, Any]) -> dict[str, bool]:
        """Send a single alert to all matching channels.

        Returns a dict of channel_name → success boolean.
        """
        severity = alert.get("severity", "info")
        results: dict[str, bool] = {}
        for channel, allowed in self._channels:
            if severity in allowed:
                results[channel.name] = channel.send(alert)
        return results

    def notify_batch(self, alerts: list[dict[str, Any]]) -> dict[str, int]:
        """Send multiple alerts.  Returns per-channel success counts."""
        counts: dict[str, int] = {}
        for alert in alerts:
            for name, ok in self.notify(alert).items():
                if ok:
                    counts[name] = counts.get(name, 0) + 1
        return counts

    @property
    def channels(self) -> list[str]:
        """Return names of registered channels."""
        return [ch.name for ch, _ in self._channels]


def _alert_payload(alert: Any) -> dict[str, Any]:
    """Normalize ORM alerts and dict alerts into dispatcher payloads."""
    if isinstance(alert, dict):
        return alert
    return {
        "id": getattr(alert, "id", None),
        "type": getattr(alert, "alert_type", "unknown"),
        "severity": getattr(alert, "severity", "info"),
        "message": getattr(alert, "message", ""),
        "entity_type": getattr(alert, "entity_type", "?"),
        "entity_id": getattr(alert, "entity_id", "?"),
        "created_at": getattr(alert, "created_at", None),
    }


def build_configured_dispatcher() -> NotificationDispatcher:
    """Build a dispatcher from configured outbound channels."""
    settings = get_settings()
    dispatcher = NotificationDispatcher()

    severities = {
        severity.strip().lower()
        for severity in settings.notification_severities.split(",")
        if severity.strip()
    } or {"critical", "warning"}

    if settings.slack_webhook_url:
        dispatcher.add_channel(
            SlackChannel(webhook_url=settings.slack_webhook_url),
            severities=severities,
        )

    if settings.notification_webhook_url:
        dispatcher.add_channel(
            WebhookChannel(url=settings.notification_webhook_url),
            severities=severities,
        )

    return dispatcher


def dispatch_alerts(alerts: list[Any]) -> dict[str, int]:
    """Dispatch alerts to configured outbound channels.

    Returns per-channel success counts. If no channels are configured, returns
    an empty dict without raising.
    """
    if not alerts:
        return {}

    dispatcher = build_configured_dispatcher()
    if not dispatcher.channels:
        return {}

    return dispatcher.notify_batch([_alert_payload(alert) for alert in alerts])
