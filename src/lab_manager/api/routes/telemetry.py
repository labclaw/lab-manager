"""Telemetry API endpoints — usage event tracking and DAU measurement."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from lab_manager.api.deps import get_db
from lab_manager.models.usage_event import UsageEvent

router = APIRouter()

# In-memory rate limiting: 1 event per user per page per minute
_rate_limits: dict[str, float] = {}


def _rate_limit_key(user_email: str, page: str) -> str:
    return f"{user_email}:{page}"


@router.post("/event")
def record_event(
    request: Request,
    event_type: str = Query(..., max_length=50),
    page: Optional[str] = Query(None, max_length=255),
    metadata: Optional[dict] = None,
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "user", "system")
    key = _rate_limit_key(user, page or "__global")

    now = time.monotonic()
    last = _rate_limits.get(key, 0)
    if now - last < 60:
        return {"status": "rate_limited"}

    _rate_limits[key] = now

    event = UsageEvent(
        user_email=user,
        event_type=event_type,
        page=page,
        metadata_=metadata,
    )
    db.add(event)
    db.commit()
    return {"status": "ok"}


@router.get("/dau")
def daily_active_users(
    days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            func.date(UsageEvent.timestamp).label("day"),
            func.count(func.distinct(UsageEvent.user_email)).label("users"),
        )
        .filter(UsageEvent.timestamp >= cutoff)
        .group_by(func.date(UsageEvent.timestamp))
        .order_by(text("day"))
        .all()
    )
    return [{"date": str(r.day), "dau": r.users} for r in rows]


@router.get("/events")
def list_events(
    event_type: Optional[str] = Query(None, max_length=50),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(UsageEvent).order_by(UsageEvent.timestamp.desc())
    if event_type:
        q = q.filter(UsageEvent.event_type == event_type)
    events = q.limit(limit).all()
    return [
        {
            "id": e.id,
            "user_email": e.user_email,
            "event_type": e.event_type,
            "page": e.page,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "metadata": e.metadata_,
        }
        for e in events
    ]
