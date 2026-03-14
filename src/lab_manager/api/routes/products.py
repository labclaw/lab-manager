"""Product CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.product import Product

router = APIRouter()


@router.get("/")
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@router.post("/", status_code=201)
def create_product(product: Product, db: Session = Depends(get_db)):
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
