"""Product CRUD endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.product import Product

router = APIRouter()


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


@router.get("/")
def list_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Product).offset(skip).limit(limit).all()


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
