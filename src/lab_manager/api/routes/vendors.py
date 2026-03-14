"""Vendor CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.vendor import Vendor

router = APIRouter()


@router.get("/")
def list_vendors(db: Session = Depends(get_db)):
    return db.query(Vendor).all()


@router.post("/", status_code=201)
def create_vendor(vendor: Vendor, db: Session = Depends(get_db)):
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
