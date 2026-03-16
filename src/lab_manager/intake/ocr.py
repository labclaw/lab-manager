"""OCR text extraction from document images."""

from __future__ import annotations

import base64
from pathlib import Path

from google import genai

from lab_manager.config import get_settings

OCR_PROMPT = """You are performing OCR on a scanned lab supply document (packing list, invoice, or shipping label).
Transcribe ALL visible text as faithfully as possible, character by character.

Critical rules:
- Output plain text only.
- Preserve reading order from top to bottom, left to right.
- Keep line breaks where they appear on the document.
- Pay extra attention to:
  * Catalog/part numbers (e.g., AB2251-1, MAB5406) — distinguish digit 1 from letter I carefully.
  * Batch/lot numbers (e.g., SDBB4556, 4361991) — include ALL batch numbers even if partially visible.
  * Handwritten text and dates (e.g., 3/9/26, 2026.3.07) — transcribe handwritten notes exactly as written.
  * PO numbers, delivery numbers, order numbers.
- Include ALL text including fine print, footer text, and handwritten annotations.
- Do not summarize or explain. Do not add any commentary.
- Do not skip any text region.
"""


_MIME_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "gif": "image/gif",
}


def _get_mime_type(filename: str) -> str:
    """Get MIME type from filename extension."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_MAP.get(suffix, f"image/{suffix}")


def extract_text_from_image(image_path: Path) -> str:
    """Run OCR on a document image and return raw text."""
    settings = get_settings()
    client = genai.Client(api_key=settings.extraction_api_key)

    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode()
    mime = _get_mime_type(image_path.name)

    response = client.models.generate_content(
        model=settings.extraction_model,
        contents=[
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": b64}},
                    {"text": OCR_PROMPT},
                ],
            },
        ],
    )
    return response.text
