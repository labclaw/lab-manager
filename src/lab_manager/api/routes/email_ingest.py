"""Email intake API endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lab_manager.api.auth import require_permission
from lab_manager.api.deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Max raw MIME email size: 50 MB
_MAX_RAW_EMAIL_BYTES = 50 * 1024 * 1024


class EmailAttachmentPayload(BaseModel):
    """A single email attachment in JSON form."""

    filename: str
    content_base64: str


class EmailIngestPayload(BaseModel):
    """JSON payload for email ingestion (pre-parsed email)."""

    sender: str
    subject: str
    body_html: Optional[str] = ""
    attachments: list[EmailAttachmentPayload] = []


def _trigger_extraction(doc_id: int) -> None:
    """Background task: run OCR + extraction on an email-ingested document."""
    from lab_manager.api.routes.documents import _run_extraction

    _run_extraction(doc_id)


@router.post(
    "/ingest",
    status_code=201,
    dependencies=[Depends(require_permission("upload_documents"))],
)
async def ingest_email(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Ingest an email for document extraction.

    Accepts either:
    - Raw MIME email (Content-Type: message/rfc822 or text/plain)
    - JSON payload with pre-parsed email fields

    Returns:
        {documents_created: N, document_ids: [...]}
    """
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()

    if content_type == "application/json":
        return await _handle_json_email(request, background_tasks, db)
    elif content_type in ("message/rfc822", "text/plain"):
        return await _handle_raw_email(request, background_tasks, db)
    else:
        return JSONResponse(
            status_code=415,
            content={
                "detail": (
                    f"Unsupported Content-Type: {content_type}. "
                    "Use 'application/json' or 'message/rfc822'."
                )
            },
        )


async def _handle_json_email(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
):
    """Handle JSON-formatted email payload."""
    from lab_manager.services.email_intake import process_email_json

    try:
        body = await request.json()
        payload = EmailIngestPayload(**body)
    except Exception as e:
        return JSONResponse(
            status_code=422,
            content={"detail": f"Invalid JSON payload: {e}"},
        )

    if not payload.attachments:
        return JSONResponse(
            status_code=422,
            content={"detail": "No attachments provided"},
        )

    documents = process_email_json(
        sender=payload.sender,
        subject=payload.subject,
        body_html=payload.body_html or "",
        attachments_b64=[att.model_dump() for att in payload.attachments],
        db=db,
    )

    # Queue background extraction for each document
    for doc in documents:
        background_tasks.add_task(_trigger_extraction, doc.id)

    return {
        "documents_created": len(documents),
        "document_ids": [doc.id for doc in documents],
    }


async def _handle_raw_email(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session,
):
    """Handle raw MIME email."""
    from lab_manager.services.email_intake import process_email

    raw_bytes = await request.body()
    if len(raw_bytes) > _MAX_RAW_EMAIL_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                "detail": (
                    f"Email too large ({len(raw_bytes)} bytes). "
                    f"Maximum: {_MAX_RAW_EMAIL_BYTES} bytes."
                )
            },
        )

    raw_email = raw_bytes.decode("utf-8", errors="replace")
    documents = process_email(raw_email, db)

    # Queue background extraction for each document
    for doc in documents:
        background_tasks.add_task(_trigger_extraction, doc.id)

    return {
        "documents_created": len(documents),
        "document_ids": [doc.id for doc in documents],
    }
