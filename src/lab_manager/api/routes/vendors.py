"""Vendor CRUD endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.exceptions import ConflictError
from lab_manager.models.order import Order
from lab_manager.models.product import Product
from lab_manager.models.vendor import Vendor

router = APIRouter()

_VENDOR_SORTABLE = {"id", "created_at", "updated_at", "name", "email", "website"}


class VendorCreate(BaseModel):
    name: str = Field(max_length=255)
    aliases: list[str] = []
    website: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
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


@router.post("/", status_code=201)
def create_vendor(body: VendorCreate, db: Session = Depends(get_db)):
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    db.flush()
    db.refresh(vendor)
    return vendor


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor(vendor_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Vendor, vendor_id, "Vendor")


@router.patch("/{vendor_id}")
def update_vendor(vendor_id: int, body: VendorUpdate, db: Session = Depends(get_db)):
    vendor = get_or_404(db, Vendor, vendor_id, "Vendor")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(vendor, key, value)
    db.flush()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=204)
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


class VendorMergeBody(BaseModel):
    """Merge one vendor into another. All references (products, orders) move to target."""

    source_vendor_id: int
    target_vendor_id: int
    add_as_alias: bool = True


@router.post("/merge")
def merge_vendors(body: VendorMergeBody, db: Session = Depends(get_db)):
    """Merge source vendor into target. Moves all products and orders.

    Scientists often end up with duplicate vendors from OCR variations
    ("Sigma-Aldrich" vs "Sigma Aldrich"). This merges them into one.
    """
    if body.source_vendor_id == body.target_vendor_id:
        raise ConflictError("Cannot merge a vendor with itself")

    source = get_or_404(db, Vendor, body.source_vendor_id, "Source vendor")
    target = get_or_404(db, Vendor, body.target_vendor_id, "Target vendor")

    # Move all products from source to target
    products_moved = 0
    source_products = db.scalars(
        select(Product).where(Product.vendor_id == source.id)
    ).all()
    for p in source_products:
        p.vendor_id = target.id
        products_moved += 1

    # Move all orders from source to target
    orders_moved = 0
    source_orders = db.scalars(
        select(Order).where(Order.vendor_id == source.id)
    ).all()
    for o in source_orders:
        o.vendor_id = target.id
        orders_moved += 1

    # Add source name as alias on target
    if body.add_as_alias:
        aliases = list(target.aliases or [])
        if source.name not in aliases and source.name != target.name:
            aliases.append(source.name)
        # Also carry over source's aliases
        for alias in source.aliases or []:
            if alias not in aliases and alias != target.name:
                aliases.append(alias)
        target.aliases = aliases

    # Delete the source vendor
    db.delete(source)
    db.flush()
    db.refresh(target)

    return {
        "merged_into": target.id,
        "target_name": target.name,
        "products_moved": products_moved,
        "orders_moved": orders_moved,
        "aliases": target.aliases,
    }


@router.get("/{vendor_id}/products")
def list_vendor_products(
    vendor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_or_404(db, Vendor, vendor_id, "Vendor")
    q = select(Product).where(Product.vendor_id == vendor_id).order_by(Product.id)
    return paginate(q, db, page, page_size)


@router.get("/{vendor_id}/orders")
def list_vendor_orders(
    vendor_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    get_or_404(db, Vendor, vendor_id, "Vendor")
    q = select(Order).where(Order.vendor_id == vendor_id).order_by(Order.id)
    return paginate(q, db, page, page_size)
