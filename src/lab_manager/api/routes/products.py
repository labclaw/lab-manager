"""Product CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.api.pagination import apply_sort, escape_like, paginate
from lab_manager.models.product import Product
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.order import OrderItem

router = APIRouter()

_PRODUCT_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "name",
    "catalog_number",
    "category",
    "vendor_id",
}


class ProductCreate(BaseModel):
    catalog_number: str
    name: str
    vendor_id: Optional[int] = None
    category: Optional[str] = None
    cas_number: Optional[str] = None
    storage_temp: Optional[str] = None
    unit: Optional[str] = None
    hazard_info: Optional[str] = None
    extra: dict = {}


class ProductUpdate(BaseModel):
    catalog_number: Optional[str] = None
    name: Optional[str] = None
    vendor_id: Optional[int] = None
    category: Optional[str] = None
    cas_number: Optional[str] = None
    storage_temp: Optional[str] = None
    unit: Optional[str] = None
    hazard_info: Optional[str] = None
    extra: Optional[dict] = None


@router.get("/")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    vendor_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    catalog_number: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if vendor_id is not None:
        q = q.filter(Product.vendor_id == vendor_id)
    if category:
        q = q.filter(Product.category.ilike(f"%{escape_like(category)}%"))
    if catalog_number:
        q = q.filter(Product.catalog_number.ilike(f"%{escape_like(catalog_number)}%"))
    if search:
        escaped = escape_like(search)
        q = q.filter(
            Product.name.ilike(f"%{escaped}%")
            | Product.catalog_number.ilike(f"%{escaped}%")
            | Product.cas_number.ilike(f"%{escaped}%")
        )
    q = apply_sort(q, Product, sort_by, sort_dir, _PRODUCT_SORTABLE)
    return paginate(q, page, page_size)


@router.post("/", status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**body.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}")
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return None


@router.get("/{product_id}/inventory")
def list_product_inventory(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    q = (
        db.query(InventoryItem)
        .filter(InventoryItem.product_id == product_id)
        .order_by(InventoryItem.id)
    )
    return paginate(q, page, page_size)


@router.get("/{product_id}/orders")
def list_product_orders(
    product_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    q = (
        db.query(OrderItem)
        .filter(OrderItem.product_id == product_id)
        .order_by(OrderItem.id)
    )
    return paginate(q, page, page_size)
