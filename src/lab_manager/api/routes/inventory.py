"""Inventory CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.inventory import InventoryItem

router = APIRouter()


@router.get("/")
def list_inventory(db: Session = Depends(get_db)):
    return db.query(InventoryItem).all()


@router.post("/", status_code=201)
def create_inventory_item(item: InventoryItem, db: Session = Depends(get_db)):
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{item_id}")
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item
