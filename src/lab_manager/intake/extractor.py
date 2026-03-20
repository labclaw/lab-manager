"""Extract structured data from OCR text using LLM + Instructor."""

from __future__ import annotations

import logging
import time

import instructor
from google import genai
from google.api_core import exceptions as gcp_exceptions

from lab_manager.config import get_settings
from lab_manager.intake.schemas import ExtractedDocument

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are extracting structured data from OCR text of a lab supply document.

Extract ALL fields you can find. Be precise — use exact text from the document.

Rules:
- vendor_name: the supplier company (e.g., "Sigma-Aldrich", "EMD Millipore Corporation")
- document_type: one of packing_list, invoice, certificate_of_analysis, shipping_label, quote, receipt, mta, other
- dates: convert to ISO format (YYYY-MM-DD) when possible
- catalog_number: exact product ID as printed
- lot_number / batch_number: exact as printed
- quantity: numeric value
- Do NOT guess or hallucinate. If a field is not visible, leave it null.
- confidence: your overall confidence (0.0-1.0) that the extraction is correct. 1.0 = all fields clearly visible and unambiguous. Below 0.7 = poor quality scan or uncertain fields.
"""

MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 120


def _call_llm(ocr_text: str) -> ExtractedDocument | None:
    """Call LLM via Instructor to extract structured data.

    Returns ExtractedDocument on success, None on permanent failure.
    Retries up to MAX_RETRIES times on transient errors (ConnectionError, TimeoutError).
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.extraction_api_key)
    client = instructor.from_genai(client)

    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=settings.extraction_model,
                messages=[
                    {
                        "role": "user",
                        "content": f"{EXTRACTION_PROMPT}\n\n---\nOCR TEXT:\n{ocr_text}",
                    },
                ],
                response_model=ExtractedDocument,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (ConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                logger.warning(
                    "Extraction transient error (attempt %d/%d): %s, retrying...",
                    attempt + 1,
                    MAX_RETRIES + 1,
                    e,
                )
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            logger.error("Extraction failed after %d retries: %s", MAX_RETRIES, e)
        except gcp_exceptions.GoogleAPIError as e:
            logger.error("Extraction API error: %s", e)
            return None
        except Exception as e:
            logger.error("Extraction unexpected error: %s", e)
            return None

    return None


def extract_from_text(ocr_text: str) -> ExtractedDocument | None:
    """Extract structured fields from OCR text.

    Returns an ExtractedDocument with all fields populated from the text,
    or None on permanent failure.
    """
    return _call_llm(ocr_text)
