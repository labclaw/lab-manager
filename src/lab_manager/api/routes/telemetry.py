"""Telemetry API endpoints -- usage event tracking and DAU measurement."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.usage_event import UsageEvent

router = APIRouter()

# In-memory rate limiting: 1 event per user per page per minute
_rate_limits: dict[str, float] = {}
_RATE_LIMIT_WINDOW = 60  # seconds
_MAX_STORE_SIZE = 10_000  # evict stale entries above this


def _rate_limit_key(user_email: str, page: str) -> str:
    return f"{user_email}:{page}"


def _evict_stale() -> None:
    """Remove entries older than the window to prevent unbounded growth."""
    if len(_rate_limits) <= _MAX_STORE_SIZE:
        return
    now = time.monotonic()
    stale = [k for k, v in _rate_limits.items() if now - v > _RATE_LIMIT_WINDOW]
    for k in stale:
        del _rate_limits[k]


@router.post("/event")
def record_event(
    request: Request,
    event_type: str = Query(..., max_length=50),
    page: Optional[str] = Query(None, max_length=255),
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "user", "system")
    key = _rate_limit_key(user, page or "__global")

    now = time.monotonic()
    last = _rate_limits.get(key, 0)
    if now - last < _RATE_LIMIT_WINDOW:
        return {"status": "rate_limited"}

    _evict_stale()
    _rate_limits[key] = now

    event = UsageEvent(
        user_email=user,
        event_type=event_type,
        page=page,
    )
    db.add(event)
    db.flush()
    return {"status": "ok"}


@router.get("/dau")
def daily_active_users(
    days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(
            func.date(UsageEvent.timestamp).label("day"),
            func.count(func.distinct(UsageEvent.user_email)).label("users"),
        )
        .where(UsageEvent.timestamp >= cutoff)
        .group_by(func.date(UsageEvent.timestamp))
        .order_by(text("day"))
    )
    rows = db.execute(stmt).all()
    return [{"date": str(r.day), "dau": r.users} for r in rows]


@router.get("/events")
def list_events(
    event_type: Optional[str] = Query(None, max_length=50),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(UsageEvent).order_by(UsageEvent.timestamp.desc())
    if event_type:
        stmt = stmt.where(UsageEvent.event_type == event_type)
    stmt = stmt.limit(limit)
    events = db.execute(stmt).scalars().all()
    return [
        {
            "id": e.id,
            "user_email": e.user_email,
            "event_type": e.event_type,
            "page": e.page,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in events
    ]
