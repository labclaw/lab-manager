"""OCR text extraction from document images."""

from __future__ import annotations

import base64
from pathlib import Path

from google import genai

from lab_manager.config import get_settings
from lab_manager.intake.prompts import OCR_PROMPT


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
