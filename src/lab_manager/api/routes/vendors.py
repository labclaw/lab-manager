"""Vendor CRUD endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.exceptions import ConflictError
from lab_manager.models.order import Order
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor
from lab_manager.services.search import index_vendor_record

router = APIRouter()

_VENDOR_SORTABLE = {"id", "created_at", "updated_at", "name", "email", "website"}


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    aliases: list[str] = []
    website: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    aliases: Optional[list[str]] = None
    website: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)


class VendorResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    aliases: list[str] = []
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    extra: dict = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


@router.get("/", dependencies=[Depends(require_permission("view_inventory"))])
def list_vendors(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = select(Vendor)
    if name:
        q = q.where(ilike_col(Vendor.name, name))
    if search:
        q = q.where(
            ilike_col(Vendor.name, search)
            | ilike_col(Vendor.email, search)
            | ilike_col(Vendor.notes, search)
        )
    q = apply_sort(q, Vendor, sort_by, sort_dir, _VENDOR_SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/", status_code=201, dependencies=[Depends(require_permission("manage_vendors"))]
)
def create_vendor(body: VendorCreate, db: Session = Depends(get_db)):
    stmt = (
        select(Vendor)
        .where(func.lower(Vendor.name) == func.lower(body.name))
        .with_for_update()
    )
    existing = db.scalars(stmt).first()
    if existing:
        raise ConflictError(f"Vendor with name '{body.name}' already exists")
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.flush()
    db.refresh(vendor)
    index_vendor_record(vendor)
    return vendor


@router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
    dependencies=[Depends(require_permission("view_inventory"))],
)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Vendor, vendor_id, "Vendor")


@router.patch(
    "/{vendor_id}", dependencies=[Depends(require_permission("manage_vendors"))]
)
def update_vendor(vendor_id: int, body: VendorUpdate, db: Session = Depends(get_db)):
    vendor = get_or_404(db, Vendor, vendor_id, "Vendor")
    updates = body.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"].lower() != vendor.name.lower():
        existing = db.scalars(
            select(Vendor)
            .where(func.lower(Vendor.name) == func.lower(updates["name"]))
            .where(Vendor.id != vendor_id)
        ).first()
        if existing:
            raise ConflictError(f"Vendor with name '{updates['name']}' already exists")
    for key, value in updates.items():
        setattr(vendor, key, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Vendor name must be unique")
    db.refresh(vendor)
    index_vendor_record(vendor)
    return vendor


@router.delete(
    "/{vendor_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_vendor(vendor_id: int, db: Session = Depends(get_db)):
    vendor = get_or_404(db, Vendor, vendor_id, "Vendor")
    try:
        db.delete(vendor)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            "Cannot delete vendor: it is referenced by products or orders"
        )
    return None


@router.get(
    "/{vendor_id}/products",
    dependencies=[Depends(require_permission("view_inventory"))],
)
def list_vendor_products(
    vendor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_or_404(db, Vendor, vendor_id, "Vendor")
    q = select(Product).where(Product.vendor_id == vendor_id).order_by(Product.id)
    return paginate(q, db, page, page_size)


@router.get(
    "/{vendor_id}/orders",
    dependencies=[Depends(require_permission("view_inventory"))],
)
def list_vendor_orders(
    vendor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_or_404(db, Vendor, vendor_id, "Vendor")
    q = select(Order).where(Order.vendor_id == vendor_id).order_by(Order.id)
    return paginate(q, db, page, page_size)
