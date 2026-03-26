"""Natural language Q&A endpoint for lab inventory.

Enhanced with suggested actions for the AI chat interface.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from lab_manager.api.deps import get_db
from lab_manager.services.rag import ask

logger = logging.getLogger(__name__)

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(..., max_length=2000)


class SuggestedAction(BaseModel):
    """A contextual action the scientist can take after seeing the answer."""

    label: str
    action_type: str  # "navigate" | "ask" | "api_call"
    target: str  # URL hash, follow-up question, or API endpoint


class AskResponse(BaseModel):
    question: str
    answer: str
    sql: Optional[str] = None
    raw_results: list = []
    row_count: Optional[int] = None
    source: str = "sql"
    suggested_actions: list[SuggestedAction] = []


def _build_suggested_actions(question: str, result: dict) -> list[SuggestedAction]:
    """Derive contextual follow-up actions from the question and results."""
    actions: list[SuggestedAction] = []
    q_lower = question.lower()
    sql_lower = (result.get("sql") or "").lower()
    row_count = result.get("row_count") or len(result.get("raw_results") or [])

    if any(
        kw in q_lower for kw in ("expir", "expire", "expiring", "shelf life", "过期")
    ):
        actions.append(
            SuggestedAction(
                label="View expiring inventory",
                action_type="navigate",
                target="/inventory",
            )
        )

    if any(
        kw in q_lower
        for kw in ("low stock", "reorder", "running out", "库存不足", "缺货")
    ):
        actions.append(
            SuggestedAction(
                label="View low-stock items",
                action_type="navigate",
                target="/inventory",
            )
        )

    if any(kw in q_lower for kw in ("order", "订单", "po number", "shipment")):
        actions.append(
            SuggestedAction(
                label="View all orders",
                action_type="navigate",
                target="/orders",
            )
        )

    if any(kw in q_lower for kw in ("review", "pending", "审核", "待审")):
        actions.append(
            SuggestedAction(
                label="Go to review queue",
                action_type="navigate",
                target="/review",
            )
        )

    if row_count and row_count > 3:
        if "inventory" in sql_lower:
            actions.append(
                SuggestedAction(
                    label="Export inventory CSV",
                    action_type="navigate",
                    target="/api/v1/export/inventory",
                )
            )
        elif "order" in sql_lower:
            actions.append(
                SuggestedAction(
                    label="Export orders CSV",
                    action_type="navigate",
                    target="/api/v1/export/orders",
                )
            )

    if any(kw in q_lower for kw in ("spend", "cost", "花费", "支出", "price")):
        actions.append(
            SuggestedAction(
                label="View spending dashboard",
                action_type="navigate",
                target="/analytics",
            )
        )

    if any(kw in q_lower for kw in ("document", "upload", "scan", "文档")):
        actions.append(
            SuggestedAction(
                label="Upload new document",
                action_type="navigate",
                target="/upload",
            )
        )

    return actions[:4]


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
    result = ask(body.question, db)
    result["suggested_actions"] = _build_suggested_actions(body.question, result)
    return result


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
    result = ask(q, db)
    result["suggested_actions"] = _build_suggested_actions(q, result)
    return result
