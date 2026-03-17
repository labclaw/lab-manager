"""Analytics / dashboard API endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.exceptions import NotFoundError
from lab_manager.services import analytics as svc

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    return svc.dashboard_summary(db)


@router.get("/spending/by-vendor")
def get_spending_by_vendor(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.spending_by_vendor(db, date_from=date_from, date_to=date_to)


@router.get("/spending/by-month")
def get_spending_by_month(
    months: int = Query(12, ge=1, le=120),
    db: Session = Depends(get_db),
):
    return svc.spending_by_month(db, months=months)


@router.get("/inventory/value")
def get_inventory_value(db: Session = Depends(get_db)):
    return svc.inventory_value(db)


@router.get("/inventory/report")
def get_inventory_report(
    location_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.inventory_report(db, location_id=location_id)


@router.get("/products/top")
def get_top_products(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return svc.top_products(db, limit=limit)


@router.get("/orders/history")
def get_order_history(
    vendor_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    return svc.order_history(
        db, vendor_id=vendor_id, date_from=date_from, date_to=date_to
    )


@router.get("/staff/activity")
def get_staff_activity(db: Session = Depends(get_db)):
    return svc.staff_activity(db)


@router.get("/vendors/{vendor_id}/summary")
def get_vendor_summary(vendor_id: int, db: Session = Depends(get_db)):
    result = svc.vendor_summary(db, vendor_id)
    if result is None:
        raise NotFoundError("Vendor", vendor_id)
    return result


@router.get("/documents/stats")
def get_document_stats(db: Session = Depends(get_db)):
    return svc.document_processing_stats(db)
