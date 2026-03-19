"""Analytics / dashboard API endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.exceptions import NotFoundError
from lab_manager.services import analytics as svc

router = APIRouter()

_Db = Depends(get_db)
_DateFrom = Query(None)
_DateTo = Query(None)
_Months = Query(12, ge=1, le=120)
_LocationId = Query(None)
_Limit = Query(20, ge=1, le=100)
_VendorId = Query(None)


@router.get("/dashboard")
def get_dashboard(db: Session = _Db):
    return svc.dashboard_summary(db)


@router.get("/spending/by-vendor")
def get_spending_by_vendor(
    date_from: date | None = _DateFrom,
    date_to: date | None = _DateTo,
    db: Session = _Db,
):
    return svc.spending_by_vendor(db, date_from=date_from, date_to=date_to)


@router.get("/spending/by-month")
def get_spending_by_month(
    months: int = _Months,
    db: Session = _Db,
):
    return svc.spending_by_month(db, months=months)


@router.get("/inventory/value")
def get_inventory_value(db: Session = _Db):
    return svc.inventory_value(db)


@router.get("/inventory/report")
def get_inventory_report(
    location_id: int | None = _LocationId,
    db: Session = _Db,
):
    return svc.inventory_report(db, location_id=location_id)


@router.get("/products/top")
def get_top_products(
    limit: int = _Limit,
    db: Session = _Db,
):
    return svc.top_products(db, limit=limit)


@router.get("/orders/history")
def get_order_history(
    vendor_id: int | None = _VendorId,
    date_from: date | None = _DateFrom,
    date_to: date | None = _DateTo,
    db: Session = _Db,
):
    return svc.order_history(db, vendor_id=vendor_id, date_from=date_from, date_to=date_to)


@router.get("/staff/activity")
def get_staff_activity(db: Session = _Db):
    return svc.staff_activity(db)


@router.get("/vendors/{vendor_id}/summary")
def get_vendor_summary(vendor_id: int, db: Session = _Db):
    result = svc.vendor_summary(db, vendor_id)
    if result is None:
        raise NotFoundError("Vendor", vendor_id)
    return result


@router.get("/documents/stats")
def get_document_stats(db: Session = _Db):
    return svc.document_processing_stats(db)
