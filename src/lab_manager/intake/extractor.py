"""Extract structured data from OCR text using LLM + Instructor."""

from __future__ import annotations

import json
import logging
import os
import time

import instructor
from google import genai
from google.genai import errors as genai_errors

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
MAX_NVIDIA_RETRIES = 5
NVIDIA_RETRY_DELAY_SECONDS = 5

EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": ["string", "null"]},
        "document_type": {
            "type": "string",
            "enum": [
                "packing_list",
                "invoice",
                "certificate_of_analysis",
                "shipping_label",
                "quote",
                "receipt",
                "mta",
                "other",
            ],
        },
        "po_number": {"type": ["string", "null"]},
        "order_number": {"type": ["string", "null"]},
        "invoice_number": {"type": ["string", "null"]},
        "delivery_number": {"type": ["string", "null"]},
        "order_date": {"type": ["string", "null"]},
        "ship_date": {"type": ["string", "null"]},
        "received_date": {"type": ["string", "null"]},
        "received_by": {"type": ["string", "null"]},
        "ship_to_address": {"type": ["string", "null"]},
        "bill_to_address": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "catalog_number": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "lot_number": {"type": ["string", "null"]},
                    "batch_number": {"type": ["string", "null"]},
                    "cas_number": {"type": ["string", "null"]},
                    "storage_temp": {"type": ["string", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                },
            },
        },
        "confidence": {"type": ["number", "null"]},
    },
    "required": ["document_type"],
}


def _is_nvidia_model(model: str) -> bool:
    return model.startswith("nvidia_nim/")


def _call_llm(ocr_text: str) -> ExtractedDocument | None:
    """Call LLM via Instructor to extract structured data.

    Returns ExtractedDocument on success, None on permanent failure.
    Retries up to MAX_RETRIES times on transient errors (ConnectionError, TimeoutError).
    """
    settings = get_settings()
    model = settings.extraction_model

    for attempt in range(MAX_RETRIES + 1):
        try:
            if _is_nvidia_model(model):
                return _extract_nvidia(ocr_text, model)

            api_key = (
                settings.extraction_api_key
                or os.environ.get("GEMINI_API_KEY", "")
                or os.environ.get("GOOGLE_API_KEY", "")
            )
            if not api_key:
                logger.error(
                    "Extraction Gemini model selected but no GEMINI_API_KEY / GOOGLE_API_KEY found"
                )
                return None

            client = genai.Client(api_key=api_key)
            client = instructor.from_genai(client)
            return client.chat.completions.create(
                model=model,
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
        except genai_errors.APIError as e:
            logger.warning("Gemini extraction failed, trying NVIDIA: %s", e)
            if settings.nvidia_build_api_key or os.environ.get(
                "NVIDIA_BUILD_API_KEY", ""
            ):
                return _extract_nvidia(
                    ocr_text, "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
                )
            logger.error("Extraction API error: %s", e)
            return None
        except Exception as e:
            logger.warning("Gemini extraction failed, trying NVIDIA: %s", e)
            if settings.nvidia_build_api_key or os.environ.get(
                "NVIDIA_BUILD_API_KEY", ""
            ):
                return _extract_nvidia(
                    ocr_text, "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
                )
            logger.error("Extraction unexpected error: %s", e)
            return None

    return None


def _extract_nvidia(ocr_text: str, model: str) -> ExtractedDocument | None:
    import httpx

    settings = get_settings()
    api_key = settings.nvidia_build_api_key or os.environ.get(
        "NVIDIA_BUILD_API_KEY", ""
    )
    if not api_key:
        logger.error(
            "Extraction NVIDIA model selected but no NVIDIA_BUILD_API_KEY found"
        )
        return None

    prompt = f"""{EXTRACTION_PROMPT}

Return ONLY valid JSON matching this schema (no markdown, no extra text):
{json.dumps(EXTRACTION_JSON_SCHEMA, indent=2)}

---
OCR TEXT:
{ocr_text}"""

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
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
            parsed = json.loads(raw)
            return ExtractedDocument(**parsed)
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429 and attempt < MAX_NVIDIA_RETRIES - 1:
                delay = NVIDIA_RETRY_DELAY_SECONDS * (2**attempt)
                logger.info(
                    "Extraction rate limited, retrying in %ds (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    MAX_NVIDIA_RETRIES,
                )
                time.sleep(delay)
                continue
            logger.error("Extraction failed: %s", e)
            return None
        except Exception as e:
            last_error = e
            logger.error("Extraction failed: %s", e)
            return None

    logger.error("Extraction failed after retries: %s", last_error)
    return None


REFINEMENT_PROMPT = """You are re-extracting structured data from OCR text of a lab supply document.

A previous extraction attempt had these issues:
{feedback}

Previous extraction result:
{previous_json}

Please re-extract carefully, paying special attention to the fields mentioned above.
Use exact text from the document. Do NOT guess or hallucinate.

Rules:
- vendor_name: the supplier company (e.g., "Sigma-Aldrich", "EMD Millipore Corporation")
- document_type: one of packing_list, invoice, certificate_of_analysis, shipping_label, quote, receipt, mta, other
- dates: convert to ISO format (YYYY-MM-DD) when possible
- catalog_number: exact product ID as printed
- lot_number / batch_number: exact as printed
- quantity: numeric value
- confidence: your overall confidence (0.0-1.0) that the extraction is correct.
"""

# Max refinement rounds to control API costs
MAX_REFINEMENT_ROUNDS = 2

# Confidence threshold below which refinement is triggered
REFINEMENT_CONFIDENCE_THRESHOLD = 0.7


def extract_with_feedback(
    ocr_text: str,
    previous: ExtractedDocument,
    feedback: str,
) -> ExtractedDocument | None:
    """Re-extract with feedback about previous attempt's issues.

    Args:
        ocr_text: Original OCR text.
        previous: Previous extraction result.
        feedback: Description of issues found in previous extraction.

    Returns:
        Improved ExtractedDocument, or None on failure.
    """
    previous_json = json.dumps(previous.model_dump(), indent=2, default=str)
    prompt = REFINEMENT_PROMPT.format(
        feedback=feedback,
        previous_json=previous_json,
    )
    full_prompt = f"{prompt}\n\n---\nOCR TEXT:\n{ocr_text}"

    settings = get_settings()
    model = settings.extraction_model

    try:
        if _is_nvidia_model(model):
            # Use NVIDIA path with refinement prompt
            return _extract_nvidia_with_prompt(ocr_text, model, full_prompt)

        api_key = (
            settings.extraction_api_key
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("GOOGLE_API_KEY", "")
        )
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)
        client = instructor.from_genai(client)
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": full_prompt}],
            response_model=ExtractedDocument,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.warning("Refinement extraction failed: %s", e)
        return None


def _extract_nvidia_with_prompt(
    ocr_text: str, model: str, prompt: str
) -> ExtractedDocument | None:
    """NVIDIA extraction with a custom prompt (used for refinement)."""
    import httpx

    settings = get_settings()
    api_key = settings.nvidia_build_api_key or os.environ.get(
        "NVIDIA_BUILD_API_KEY", ""
    )
    if not api_key:
        return None

    full_prompt = (
        f"{prompt}\n\n"
        f"Return ONLY valid JSON matching this schema (no markdown, no extra text):\n"
        f"{json.dumps(EXTRACTION_JSON_SCHEMA, indent=2)}"
    )

    try:
        resp = httpx.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model.removeprefix("nvidia_nim/"),
                "messages": [{"role": "user", "content": full_prompt}],
                "max_tokens": 4096,
                "temperature": 0.1,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        parsed = json.loads(raw)
        return ExtractedDocument(**parsed)
    except Exception as e:
        logger.warning("NVIDIA refinement failed: %s", e)
        return None


def extract_from_text(ocr_text: str) -> ExtractedDocument | None:
    """Extract structured fields from OCR text.

    Returns an ExtractedDocument with all fields populated from the text,
    or None on permanent failure.
    """
    return _call_llm(ocr_text)
