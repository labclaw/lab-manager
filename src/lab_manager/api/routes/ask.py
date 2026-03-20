"""Natural language Q&A endpoint for lab inventory."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from lab_manager.api.deps import get_db
from lab_manager.services.rag import ask

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: Optional[str] = None
    raw_results: list = []
    row_count: Optional[int] = None
    source: str = "sql"


@router.post("", response_model=AskResponse)
@router.post("/", response_model=AskResponse, include_in_schema=False)
def ask_post(
    request: Request,
    body: AskRequest,
    db: Session = Depends(get_db),
):
    """Ask a natural language question about lab inventory (POST).

    Rate limited to 10 requests per minute via slowapi.
    """
    return ask(body.question, db)


@router.get("", response_model=AskResponse)
@router.get("/", response_model=AskResponse, include_in_schema=False)
def ask_get(
    request: Request,
    q: str = Query(..., description="Question in plain English or Chinese"),
    db: Session = Depends(get_db),
):
    """Ask a natural language question about lab inventory (GET).

    Rate limited to 10 requests per minute via slowapi.
    """
    return ask(q, db)
