"""Extract structured data from OCR text using LLM + Instructor."""

from __future__ import annotations

import instructor
from google import genai

from lab_manager.config import get_settings
from lab_manager.intake.schemas import ExtractedDocument

EXTRACTION_PROMPT = """You are extracting structured data from OCR text of a lab supply document (packing list, invoice, or shipping label).

Extract ALL fields you can find. Be precise — use exact text from the document.

Rules:
- vendor_name: the supplier company (e.g., "Sigma-Aldrich", "EMD Millipore Corporation")
- document_type: one of packing_list, invoice, package, shipping_label
- dates: convert to ISO format (YYYY-MM-DD) when possible
- catalog_number: exact product ID as printed
- lot_number / batch_number: exact as printed
- quantity: numeric value
- Do NOT guess or hallucinate. If a field is not visible, leave it null.
"""


def _call_llm(ocr_text: str) -> ExtractedDocument:
    """Call LLM via Instructor to extract structured data."""
    settings = get_settings()
    client = genai.Client(api_key=settings.extraction_api_key)
    client = instructor.from_genai(client)

    return client.chat.completions.create(
        model=settings.extraction_model,
        messages=[
            {
                "role": "user",
                "content": f"{EXTRACTION_PROMPT}\n\n---\nOCR TEXT:\n{ocr_text}",
            },
        ],
        response_model=ExtractedDocument,
    )


def extract_from_text(ocr_text: str) -> ExtractedDocument:
    """Extract structured fields from OCR text.

    Returns an ExtractedDocument with all fields populated from the text.
    """
    return _call_llm(ocr_text)
