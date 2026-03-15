"""Vendor CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import apply_sort, escape_like, paginate
from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.order import Order

router = APIRouter()

_VENDOR_SORTABLE = {"id", "created_at", "updated_at", "name", "email", "website"}


class VendorCreate(BaseModel):
    name: str
    aliases: list[str] = []
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    aliases: Optional[list[str]] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
def list_vendors(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = db.query(Vendor)
    if name:
        q = q.filter(Vendor.name.ilike(f"%{escape_like(name)}%", escape="\\"))
    if search:
        escaped = escape_like(search)
        q = q.filter(
            Vendor.name.ilike(f"%{escaped}%", escape="\\")
            | Vendor.email.ilike(f"%{escaped}%", escape="\\")
            | Vendor.notes.ilike(f"%{escaped}%", escape="\\")
        )
    q = apply_sort(q, Vendor, sort_by, sort_dir, _VENDOR_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_vendor(body: VendorCreate, db: Session = Depends(get_db)):
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.get("/{vendor_id}")
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.patch("/{vendor_id}")
def update_vendor(vendor_id: int, body: VendorUpdate, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    try:
        db.delete(vendor)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete vendor: it is referenced by products or orders",
        )
    return None


@router.get("/{vendor_id}/products")
def list_vendor_products(
    vendor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    q = db.query(Product).filter(Product.vendor_id == vendor_id).order_by(Product.id)
    return paginate(q, page, page_size)


@router.get("/{vendor_id}/orders")
def list_vendor_orders(
    vendor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    q = db.query(Order).filter(Order.vendor_id == vendor_id).order_by(Order.id)
    return paginate(q, page, page_size)
