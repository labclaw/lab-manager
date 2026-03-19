"""Telemetry endpoints for usage tracking and DAU measurement."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.usage_event import UsageEvent

router = APIRouter()

_rate_limit_store: dict[str, float] = {}
_RATE_LIMIT_WINDOW = 60  # seconds


def _is_rate_limited(user_email: str, page: Optional[str]) -> bool:
    key = f"{user_email}:{page or ""}"
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW
    stale = [k for k, v in _rate_limit_store.items() if v < cutoff]
    for k in stale:
        del _rate_limit_store[k]
    last = _rate_limit_store.get(key, 0)
    if now - last < _RATE_LIMIT_WINDOW:
        return True
    _rate_limit_store[key] = now
    return False


@router.post("/event")
def record_event(request: Request, body: dict, db: Session = Depends(get_db)):
    user = getattr(request.state, "user", None)
    user_email = getattr(request.state, "user_email", None) or user
    if not user or user in ("system", "api-client"):
        raise HTTPException(status_code=401, detail="Authentication required")

    event_type = body.get("event_type", "")
    if event_type not in ("login", "page_view", "action"):
        raise HTTPException(status_code=422, detail="Invalid event_type")

    page = body.get("page")
    if _is_rate_limited(user_email, page):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    metadata_raw = body.get("metadata")
    metadata_json = json.dumps(metadata_raw) if metadata_raw is not None else None

    event = UsageEvent(
        user_email=user_email,
        event_type=event_type,
        page=page,
        metadata_json=metadata_json,
    )
    db.add(event)
    db.commit()
    return {"status": "ok"}


@router.get("/dau")
def get_dau(days: int = Query(30, ge=1, le=90), db: Session = Depends(get_db)):
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
    request: Request,
    event_type: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    user = getattr(request.state, "user", None)
    if not user or user in ("system", "api-client"):
        raise HTTPException(status_code=401, detail="Authentication required")

    q = db.query(UsageEvent)
    if event_type:
        q = q.filter(UsageEvent.event_type == event_type)
    if user_email:
        q = q.filter(UsageEvent.user_email == user_email)
    q = q.order_by(UsageEvent.timestamp.desc())

    skip = (page - 1) * page_size
    items = q.offset(skip).limit(page_size).all()
    total = q.offset(0).limit(None).count()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
