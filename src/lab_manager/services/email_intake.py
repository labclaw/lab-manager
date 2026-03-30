"""Email-to-intake agent: parse vendor emails and create Document records.

PI forwards a vendor email -> system auto-extracts order/shipping info ->
adds to review queue (same as upload flow).
"""

from __future__ import annotations

import base64
import email
import email.policy
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.models.document import Document, DocumentStatus

logger = logging.getLogger(__name__)

# Attachment types we process
_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/tiff"}
_PDF_CONTENT_TYPES = {"application/pdf"}
_SUPPORTED_CONTENT_TYPES = _IMAGE_CONTENT_TYPES | _PDF_CONTENT_TYPES

# Size limits
_MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024  # 50 MB per attachment
_MAX_ATTACHMENTS = 20


@dataclass
class Attachment:
    """Parsed email attachment."""

    filename: str
    content_type: str
    data: bytes


@dataclass
class ParsedEmail:
    """Parsed email metadata and content."""

    sender: str
    subject: str
    date: Optional[str]
    body_text: str
    body_html: str
    attachments: list[Attachment] = field(default_factory=list)


def parse_email(raw_email: str) -> ParsedEmail:
    """Parse a raw MIME email string into structured components.

    Args:
        raw_email: Raw MIME email as string.

    Returns:
        ParsedEmail with sender, subject, date, body, and attachments.
    """
    msg = email.message_from_string(raw_email, policy=email.policy.default)

    sender = str(msg.get("From", ""))
    subject = str(msg.get("Subject", ""))
    date_str = str(msg.get("Date", "")) or None

    body_text = ""
    body_html = ""
    attachments: list[Attachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # Attachment (has filename or explicit attachment disposition)
            if part.get_filename() or "attachment" in disposition.lower():
                _extract_attachment(part, attachments)
                continue

            # Body parts
            if content_type == "text/plain" and not body_text:
                payload = part.get_content()
                body_text = payload if isinstance(payload, str) else str(payload)
            elif content_type == "text/html" and not body_html:
                payload = part.get_content()
                body_html = payload if isinstance(payload, str) else str(payload)
    else:
        content_type = msg.get_content_type()
        payload = msg.get_content()
        content = payload if isinstance(payload, str) else str(payload)
        if content_type == "text/html":
            body_html = content
        else:
            body_text = content

    return ParsedEmail(
        sender=sender,
        subject=subject,
        date=date_str if date_str else None,
        body_text=body_text,
        body_html=body_html,
        attachments=attachments,
    )


def _extract_attachment(part: EmailMessage, attachments: list[Attachment]) -> None:
    """Extract a single attachment from an email part."""
    if len(attachments) >= _MAX_ATTACHMENTS:
        logger.warning("Max attachments (%d) reached, skipping", _MAX_ATTACHMENTS)
        return

    filename = part.get_filename() or "unnamed_attachment"
    content_type = part.get_content_type()
    payload = part.get_payload(decode=True)

    if payload is None:
        logger.warning("Empty payload for attachment %s", filename)
        return

    if len(payload) > _MAX_ATTACHMENT_BYTES:
        logger.warning(
            "Attachment %s too large (%d bytes), skipping",
            filename,
            len(payload),
        )
        return

    attachments.append(
        Attachment(filename=filename, content_type=content_type, data=payload)
    )


def extract_attachments(parsed: ParsedEmail) -> list[Attachment]:
    """Filter attachments to only supported types (PDF, PNG, JPG, TIFF).

    Args:
        parsed: ParsedEmail from parse_email().

    Returns:
        List of Attachment objects with supported content types.
    """
    supported = []
    for att in parsed.attachments:
        if att.content_type in _SUPPORTED_CONTENT_TYPES:
            supported.append(att)
        else:
            logger.info(
                "Skipping unsupported attachment type %s for %s",
                att.content_type,
                att.filename,
            )
    return supported


def _sanitize_filename(name: str) -> str:
    """Sanitize attachment filename for safe storage."""
    safe = name.replace("/", "_").replace("\\", "_").replace("\x00", "")
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    if not safe or safe.startswith("."):
        safe = "attachment" + safe
    return safe


def _save_attachment(att: Attachment, upload_dir: Path) -> tuple[Path, str]:
    """Save attachment bytes to upload directory with dedup.

    Returns:
        Tuple of (file_path, saved_filename).
    """
    upload_dir.mkdir(parents=True, exist_ok=True)
    content_hash = hashlib.sha256(att.data).hexdigest()[:16]
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    usec = f"{now.microsecond:06d}"

    safe_name = _sanitize_filename(att.filename)
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix
    saved_name = f"{timestamp}_{usec}_email_{stem}_{content_hash}{suffix}"

    dest = upload_dir / saved_name
    dest.write_bytes(att.data)
    return dest, saved_name


def process_email(raw_email: str, db: Session) -> list[Document]:
    """Full email-to-intake pipeline.

    1. Parse email (sender, subject, date, body)
    2. Extract supported attachments (PDFs, images)
    3. For each attachment: create Document record with source="email"
    4. Queue for OCR/extraction (same as upload flow)

    Args:
        raw_email: Raw MIME email string.
        db: SQLAlchemy session.

    Returns:
        List of Document records created.
    """
    parsed = parse_email(raw_email)
    attachments = extract_attachments(parsed)

    if not attachments:
        logger.info(
            "No supported attachments in email from=%s subject=%s",
            parsed.sender,
            parsed.subject,
        )
        return []

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    documents: list[Document] = []

    email_metadata = {
        "source": "email",
        "email_from": parsed.sender,
        "email_subject": parsed.subject,
        "email_date": parsed.date,
    }

    for att in attachments:
        dest, saved_name = _save_attachment(att, upload_dir)

        doc = Document(
            file_path=str(dest),
            file_name=saved_name,
            status=DocumentStatus.processing,
            review_notes=(
                f"Email intake: from={parsed.sender}, subject={parsed.subject}"
            ),
            extracted_data=email_metadata,
        )
        db.add(doc)
        db.flush()

        logger.info(
            "Created document %d from email attachment %s (from=%s)",
            doc.id,
            att.filename,
            parsed.sender,
        )
        documents.append(doc)

    # Let the caller (get_db dependency) own the commit lifecycle.
    # Flush is sufficient to get auto-generated IDs; the route or
    # dependency injector will commit once the full request succeeds.
    if documents:
        for doc in documents:
            db.refresh(doc)

    return documents


def process_email_json(
    sender: str,
    subject: str,
    body_html: str,
    attachments_b64: list[dict],
    db: Session,
) -> list[Document]:
    """Process email from JSON payload (pre-parsed).

    Args:
        sender: Email sender address.
        subject: Email subject line.
        body_html: HTML body content.
        attachments_b64: List of {"filename": str, "content_base64": str}.
        db: SQLAlchemy session.

    Returns:
        List of Document records created.
    """
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    documents: list[Document] = []

    email_metadata = {
        "source": "email",
        "email_from": sender,
        "email_subject": subject,
    }

    for att_data in attachments_b64:
        filename = att_data.get("filename", "unnamed.bin")
        content_b64 = att_data.get("content_base64", "")

        try:
            data = base64.b64decode(content_b64)
        except Exception:
            logger.warning("Failed to decode base64 for attachment %s", filename)
            continue

        if len(data) > _MAX_ATTACHMENT_BYTES:
            logger.warning("Attachment %s too large, skipping", filename)
            continue

        # Infer content type from extension
        ext = Path(filename).suffix.lower()
        content_type_map = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        content_type = content_type_map.get(ext)
        if not content_type:
            logger.info("Skipping unsupported file type: %s", filename)
            continue

        att = Attachment(filename=filename, content_type=content_type, data=data)
        dest, saved_name = _save_attachment(att, upload_dir)

        doc = Document(
            file_path=str(dest),
            file_name=saved_name,
            status=DocumentStatus.processing,
            review_notes=f"Email intake: from={sender}, subject={subject}",
            extracted_data=email_metadata,
        )
        db.add(doc)
        db.flush()

        logger.info(
            "Created document %d from JSON email attachment %s",
            doc.id,
            filename,
        )
        documents.append(doc)

    # Let the caller (get_db dependency) own the commit lifecycle.
    if documents:
        for doc in documents:
            db.refresh(doc)

    return documents
