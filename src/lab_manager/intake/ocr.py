"""OCR text extraction from document images.

Supports tiered detection:
- "local": Use local vLLM model (DeepSeek-OCR, PaddleOCR-VL, etc.) — fast, free
- "api":   Use cloud API (Gemini, Mistral OCR 3, NVIDIA) — accurate, paid
- "auto":  Try local first, fall back to API on failure (default)
"""

from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors

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

MAX_NVIDIA_RETRIES = 5
NVIDIA_RETRY_DELAY_SECONDS = 5

_VALID_TIERS = ("local", "api", "auto")


def _get_mime_type(filename: str) -> str:
    """Get MIME type from filename extension."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_MAP.get(suffix, f"image/{suffix}")


def _is_nvidia_model(model: str) -> bool:
    return isinstance(model, str) and model.startswith("nvidia_nim/")


def _get_ocr_model(settings) -> str:
    ocr_model = getattr(settings, "ocr_model", None)
    if isinstance(ocr_model, str) and ocr_model.strip():
        return ocr_model
    return settings.extraction_model


def _response_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    choices = getattr(response, "choices", None)
    if choices and len(choices) > 0:
        msg = getattr(choices[0], "message", None)
        content = getattr(msg, "content", None) if msg else None
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif hasattr(item, "text"):
                    parts.append(item.text)
            return "\n".join(part for part in parts if part).strip()
        if content is not None:
            return str(content).strip()

    return ""


# ---------------------------------------------------------------------------
# Local OCR (vLLM-based models)
# ---------------------------------------------------------------------------


def _ocr_local(image_path: Path, settings) -> str:
    """Run OCR via a local vLLM model from the provider registry."""
    from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS, get_provider

    provider_name = getattr(settings, "ocr_local_model", "deepseek_ocr")
    if provider_name not in OCR_PROVIDERS:
        raise RuntimeError(
            f"Unknown local OCR provider: {provider_name}. "
            f"Available: {list(OCR_PROVIDERS.keys())}"
        )

    provider = get_provider(provider_name, OCR_PROVIDERS)

    # Override base_url from settings if the provider supports it
    local_url = getattr(settings, "ocr_local_url", "")
    if local_url and hasattr(provider, "base_url"):
        provider.base_url = local_url

    logger.info("OCR local: using %s for %s", provider_name, image_path.name)
    text = provider.extract_text(str(image_path))
    if not text:
        raise RuntimeError(f"Local OCR ({provider_name}) returned empty text")
    return text


# ---------------------------------------------------------------------------
# API OCR (cloud providers)
# ---------------------------------------------------------------------------


def _ocr_gemini(image_path: Path, settings) -> str:
    api_key = (
        settings.extraction_api_key
        or settings.gemini_api_key
        or settings.google_api_key
    )
    if not api_key:
        raise RuntimeError("No Gemini OCR key configured")

    client = genai.Client(api_key=api_key)
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
    text = _response_text(response)
    if not text:
        raise RuntimeError("Gemini OCR returned empty text")
    return text


def _ocr_nvidia(image_path: Path, settings, model: str) -> str:
    import httpx

    api_key = settings.nvidia_build_api_key
    if not api_key:
        raise RuntimeError("No NVIDIA OCR key configured")

    image_bytes = image_path.read_bytes()
    b64 = base64.b64encode(image_bytes).decode()
    mime = _get_mime_type(image_path.name)

    last_error: Exception | None = None
    for attempt in range(MAX_NVIDIA_RETRIES):
        try:
            resp = httpx.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model.removeprefix("nvidia_nim/"),
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                                },
                                {"type": "text", "text": OCR_PROMPT},
                            ],
                        }
                    ],
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError("NVIDIA OCR returned empty choices")
            content = choices[0].get("message", {}).get("content", "")
            return content
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429 and attempt < MAX_NVIDIA_RETRIES - 1:
                delay = NVIDIA_RETRY_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "NVIDIA OCR rate limited, retrying in %ds (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    MAX_NVIDIA_RETRIES,
                )
                time.sleep(delay)
                continue
            raise
        except Exception as e:
            last_error = e
            raise RuntimeError(f"NVIDIA OCR failed: {e}") from e

    raise RuntimeError(f"NVIDIA OCR failed after retries: {last_error}")


def _ocr_api(image_path: Path, settings) -> str:
    """Run OCR via cloud API with fallback chain: Gemini → NVIDIA."""
    model = _get_ocr_model(settings)

    if _is_nvidia_model(model):
        return _ocr_nvidia(image_path, settings, model)

    try:
        return _ocr_gemini(image_path, settings)
    except Exception as e:
        logger.warning("Gemini OCR failed, trying NVIDIA fallback: %s", e)
        if settings.nvidia_build_api_key:
            return _ocr_nvidia(
                image_path,
                settings,
                "nvidia_nim/meta/llama-3.2-90b-vision-instruct",
            )
        raise


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_text_from_image(image_path: Path) -> str:
    """Run OCR on a document image and return raw text.

    Uses tiered detection controlled by OCR_TIER setting:
    - "local": vLLM model only (fast, free, requires local GPU)
    - "api":   Cloud API only (Gemini/NVIDIA, accurate, paid)
    - "auto":  Try local first, fall back to API on failure (default)

    Returns empty string on any failure with error details logged.
    """
    try:
        settings = get_settings()
        tier = getattr(settings, "ocr_tier", "auto")
        if tier not in _VALID_TIERS:
            logger.warning("Invalid OCR_TIER=%s, defaulting to 'auto'", tier)
            tier = "auto"

        if tier == "local":
            return _ocr_local(image_path, settings)

        if tier == "api":
            return _ocr_api(image_path, settings)

        # tier == "auto": try local first, fall back to API
        try:
            text = _ocr_local(image_path, settings)
            if text:
                return text
        except Exception as e:
            logger.info(
                "Local OCR failed for %s, falling back to API: %s",
                image_path.name,
                e,
            )

        return _ocr_api(image_path, settings)

    except FileNotFoundError:
        logger.error("OCR file not found: %s", image_path)
        return ""
    except genai_errors.APIError as e:
        logger.error("OCR API error for %s: %s", image_path.name, e)
        return ""
    except Exception as e:
        logger.error("OCR unexpected error for %s: %s", image_path.name, e)
        return ""
