"""OCR text extraction from document images."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from google import genai
from google.api_core import exceptions as gcp_exceptions

from lab_manager.config import get_settings
from lab_manager.intake.prompts import OCR_PROMPT

logger = logging.getLogger(__name__)

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
    """Run OCR on a document image and return raw text.

    Returns empty string on any failure (file not found, API error, etc.)
    with error details logged.
    """
    try:
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

        if response.text is None:
            logger.warning("OCR returned None text for %s", image_path.name)
            return ""
        return response.text

    except FileNotFoundError:
        logger.error("OCR file not found: %s", image_path)
        return ""
    except gcp_exceptions.GoogleAPIError as e:
        logger.error("OCR API error for %s: %s", image_path.name, e)
        return ""
    except Exception as e:
        logger.error("OCR unexpected error for %s: %s", image_path.name, e)
        return ""
