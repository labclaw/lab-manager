"""Test alert deduplication: persist_alerts must not create duplicate unresolved alerts."""

from __future__ import annotations

from lab_manager.models.alert import Alert
from lab_manager.models.document import Document
from lab_manager.services.alerts import persist_alerts


def test_persist_alerts_no_duplicates(db_session):
    """Two sequential persist_alerts calls must not duplicate unresolved alerts."""
    doc = Document(
        file_path="uploads/race.jpg",
        file_name="race.jpg",
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()

    created1, _ = persist_alerts(db_session)
    db_session.commit()

    created2, _ = persist_alerts(db_session)
    db_session.commit()

    pending1 = [a for a in created1 if a.alert_type == "pending_review"]
    pending2 = [a for a in created2 if a.alert_type == "pending_review"]
    assert len(pending1) >= 1
    assert len(pending2) == 0

    from sqlalchemy import select as sa_select

    all_unresolved = (
        db_session.execute(
            sa_select(Alert).where(
                Alert.is_resolved.is_(False),
                Alert.alert_type == "pending_review",
                Alert.entity_type == "document",
                Alert.entity_id == doc.id,
            )
        )
        .scalars()
        .all()
    )
    assert len(all_unresolved) == 1
