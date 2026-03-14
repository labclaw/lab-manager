"""Natural language Q&A endpoint for lab inventory."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.deps import get_db
from lab_manager.services.rag import ask

router = APIRouter()


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: Optional[str] = None
    raw_results: list = []
    source: str = "sql"


@router.post("", response_model=AskResponse)
@router.post("/", response_model=AskResponse, include_in_schema=False)
def ask_post(body: AskRequest, db: Session = Depends(get_db)):
    """Ask a natural language question about lab inventory (POST)."""
    return ask(body.question, db)


@router.get("", response_model=AskResponse)
@router.get("/", response_model=AskResponse, include_in_schema=False)
def ask_get(
    q: str = Query(..., description="Question in plain English or Chinese"),
    db: Session = Depends(get_db),
):
    """Ask a natural language question about lab inventory (GET)."""
    return ask(q, db)
