"""Test that resolved alerts are not recreated on next check cycle.

Regression test for: persist_alerts() only checked unresolved alerts
when building existing_keys, so a resolved alert would be re-created
as a brand new alert on the next check cycle (alert spam).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select as sa_select

from lab_manager.models.alert import Alert
from lab_manager.models.document import Document
from lab_manager.services.alerts import persist_alerts


def test_resolved_alert_not_recreated_immediately(db_session):
    """After resolving an alert, the next persist_alerts call must NOT
    recreate it (because the resolved alert is within the 7-day window)."""
    doc = Document(
        file_path="uploads/recreate_test.jpg",
        file_name="recreate_test.jpg",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # First call: creates the alert
    created1, _ = persist_alerts(db_session)
    db_session.commit()
    pending_review1 = [a for a in created1 if a.alert_type == "pending_review"]
    assert len(pending_review1) >= 1, "First call should create at least one alert"

    alert = pending_review1[0]

    # Resolve the alert
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    db_session.commit()

    # Second call: should NOT recreate the alert (resolved within 7 days)
    created2, _ = persist_alerts(db_session)
    db_session.commit()
    pending_review2 = [a for a in created2 if a.alert_type == "pending_review"]
    assert len(pending_review2) == 0, (
        "Resolved alert should NOT be recreated within 7-day window"
    )

    # Verify only the original resolved alert exists for this entity
    all_alerts = (
        db_session.execute(
            sa_select(Alert).where(
                Alert.alert_type == "pending_review",
                Alert.entity_type == "document",
                Alert.entity_id == doc.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(all_alerts) == 1, "Should still be exactly 1 alert (the resolved one)"
    assert all_alerts[0].is_resolved is True


def test_resolved_alert_reopened_after_7_days(db_session):
    """If an alert was resolved more than 7 days ago and the condition
    persists, persist_alerts SHOULD reopen the old resolved alert."""
    doc = Document(
        file_path="uploads/recreate_old.jpg",
        file_name="recreate_old.jpg",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # Create a resolved alert with resolved_at = 8 days ago
    alert = Alert(
        alert_type="pending_review",
        severity="info",
        message="Old resolved alert",
        entity_type="document",
        entity_id=doc.id,
        is_resolved=True,
        resolved_at=datetime.now(timezone.utc) - timedelta(days=8),
    )
    db_session.add(alert)
    db_session.commit()

    # persist_alerts should reopen the old alert (7-day window expired)
    created, _ = persist_alerts(db_session)
    db_session.commit()
    pending_review = [a for a in created if a.alert_type == "pending_review"]
    assert len(pending_review) >= 1, (
        "Alert should be reopened when resolved > 7 days ago"
    )

    # The reopened alert should be the same one (reused, not a new one)
    reopened = pending_review[0]
    assert reopened.is_resolved is False
    assert reopened.message == "Old resolved alert" or reopened.id == alert.id
