"""Document CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.models.document import Document

router = APIRouter()


@router.get("/")
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).all()


@router.post("/", status_code=201)
def create_document(document: Document, db: Session = Depends(get_db)):
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
