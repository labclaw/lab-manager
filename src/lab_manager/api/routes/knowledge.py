"""Knowledge base CRUD and search endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db, get_or_404
from lab_manager.api.pagination import apply_sort, ilike_col, paginate
from lab_manager.models.knowledge import KnowledgeCategory

router = APIRouter()

_VALID_CATEGORIES = {c.value for c in KnowledgeCategory}

_SORTABLE = {
    "id",
    "created_at",
    "updated_at",
    "title",
    "category",
}


class KnowledgeCreate(BaseModel):
    title: str = Field(max_length=500)
    category: str = Field(default="general", max_length=50)
    content: str
    tags: list[str] = Field(default_factory=list)
    source_type: Optional[str] = Field(default=None, max_length=100)
    source_url: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in _VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_VALID_CATEGORIES)}")
        return v


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=50)
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    source_type: Optional[str] = Field(default=None, max_length=100)
    source_url: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(_VALID_CATEGORIES)}")
        return v


@router.get("/")
def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    from lab_manager.models.knowledge import KnowledgeEntry

    q = select(KnowledgeEntry).where(KnowledgeEntry.is_deleted.is_(False))
    if category:
        q = q.where(KnowledgeEntry.category == category)
    if search:
        q = q.where(
            ilike_col(KnowledgeEntry.title, search)
            | ilike_col(KnowledgeEntry.content, search)
        )
    q = apply_sort(q, KnowledgeEntry, sort_by, sort_dir, _SORTABLE)
    return paginate(q, db, page, page_size)


@router.post(
    "/",
    status_code=201,
    dependencies=[Depends(require_permission("upload_documents"))],
)
def create_knowledge(body: KnowledgeCreate, db: Session = Depends(get_db)):
    from lab_manager.models.knowledge import KnowledgeEntry

    entry = KnowledgeEntry(**body.model_dump())
    db.add(entry)
    db.flush()
    db.refresh(entry)
    return entry


@router.get("/search")
def search_knowledge(
    q: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    from lab_manager.models.knowledge import KnowledgeEntry

    stmt = select(KnowledgeEntry).where(
        KnowledgeEntry.is_deleted.is_(False),
        or_(
            ilike_col(KnowledgeEntry.title, q),
            ilike_col(KnowledgeEntry.content, q),
        ),
    )
    if category:
        stmt = stmt.where(KnowledgeEntry.category == category)
    return paginate(stmt, db, page, page_size)


@router.get("/{entry_id}")
def get_knowledge(entry_id: int, db: Session = Depends(get_db)):
    from lab_manager.models.knowledge import KnowledgeEntry

    return get_or_404(db, KnowledgeEntry, entry_id, "KnowledgeEntry")


@router.patch(
    "/{entry_id}",
    dependencies=[Depends(require_permission("upload_documents"))],
)
def update_knowledge(
    entry_id: int, body: KnowledgeUpdate, db: Session = Depends(get_db)
):
    from lab_manager.models.knowledge import KnowledgeEntry

    entry = get_or_404(db, KnowledgeEntry, entry_id, "KnowledgeEntry")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.flush()
    db.refresh(entry)
    return entry


@router.delete(
    "/{entry_id}",
    status_code=204,
    dependencies=[Depends(require_permission("delete_records"))],
)
def delete_knowledge(entry_id: int, db: Session = Depends(get_db)):
    from lab_manager.models.knowledge import KnowledgeEntry

    entry = get_or_404(db, KnowledgeEntry, entry_id, "KnowledgeEntry")
    entry.is_deleted = True
    db.flush()
    return None
