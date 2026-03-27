"""Ginkgo AI Model API client for protein/DNA sequence analysis.

Public self-service API at models.ginkgobioworks.ai.
Supports: ESM2 (protein LM), AA0 (Ginkgo protein LM), 3UTR, Promoter-0,
ABdiffusion (antibody design), LCDNA (long-context DNA).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://models.ginkgobioworks.ai"
_TIMEOUT = 30.0
_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_MAX = 1024

_MIN_INTERVAL = 0.2  # 200ms between requests
_last_request_time: float = 0.0

# Known models from the Ginkgo AI platform
MODELS: list[dict[str, str]] = [
    {
        "id": "ginkgo-aa0-650M",
        "name": "AA0 650M",
        "type": "protein_language_model",
        "description": "Ginkgo's protein language model (650M parameters)",
    },
    {
        "id": "meta/esm2-3b",
        "name": "ESM2 3B",
        "type": "protein_language_model",
        "description": "Meta's ESM2 protein language model (3B parameters)",
    },
    {
        "id": "ginkgo-3utr",
        "name": "3UTR",
        "type": "mrna_model",
        "description": "3' UTR language model for mRNA design",
    },
    {
        "id": "ginkgo-promoter-0",
        "name": "Promoter-0",
        "type": "dna_model",
        "description": "DNA promoter activity prediction model",
    },
    {
        "id": "ginkgo-abdiffusion",
        "name": "ABdiffusion",
        "type": "antibody_design",
        "description": "Antibody design via diffusion model",
    },
    {
        "id": "ginkgo-lcdna",
        "name": "LCDNA",
        "type": "dna_model",
        "description": "Long-context DNA sequence analysis model",
    },
]


def _rate_limit() -> None:
    """Enforce minimum interval between requests."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _get_api_key() -> str:
    """Get the Ginkgo AI API key from settings."""
    from lab_manager.config import get_settings

    return get_settings().ginkgo_ai_api_key


def _get_base_url() -> str:
    """Get the Ginkgo AI base URL from settings."""
    from lab_manager.config import get_settings

    return get_settings().ginkgo_ai_base_url or _BASE_URL


def _call_api(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Core HTTP call to Ginkgo AI API with error handling.

    Returns parsed JSON dict or None on failure.
    """
    api_key = _get_api_key()
    base_url = _get_base_url()

    if not api_key:
        logger.warning("Ginkgo AI API key not configured")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    _rate_limit()
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            if method.upper() == "GET":
                resp = client.get(f"{base_url}{path}", headers=headers)
            else:
                resp = client.post(f"{base_url}{path}", headers=headers, json=payload)

            if resp.status_code == 401:
                logger.warning("Ginkgo AI API: authentication failed (401)")
                return None
            if resp.status_code == 429:
                logger.warning("Ginkgo AI API: rate limit exceeded (429)")
                return None
            if resp.status_code == 404:
                logger.warning("Ginkgo AI API: resource not found (404)")
                return None
            resp.raise_for_status()
            return resp.json()

    except httpx.TimeoutException:
        logger.warning("Ginkgo AI API: request timed out for %s %s", method, path)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Ginkgo AI API: HTTP %s for %s %s",
            exc.response.status_code,
            method,
            path,
        )
        return None
    except Exception:
        logger.exception("Ginkgo AI API: unexpected error for %s %s", method, path)
        return None


def list_models() -> list[dict[str, str]]:
    """Return the static list of available Ginkgo AI models."""
    return list(MODELS)


def analyze_sequence(
    sequence: str,
    model: str = "ginkgo-aa0-650M",
    analysis_type: str = "masked_inference",
) -> dict[str, Any]:
    """Analyze a protein or DNA sequence using Ginkgo AI models.

    Args:
        sequence: The biological sequence string (protein or DNA).
        model: Model ID to use (default: ginkgo-aa0-650M).
        analysis_type: "masked_inference" or "embedding".

    Returns:
        Dict with analysis results, or empty dict on failure.
    """
    if not sequence or not sequence.strip():
        return {}

    cache_key = f"{model}|{analysis_type}|{sequence}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    payload: dict[str, Any] = {
        "model": model,
        "sequence": sequence.strip(),
    }

    if analysis_type == "masked_inference":
        path = "/v1/inference/masked"
    elif analysis_type == "embedding":
        path = "/v1/inference/embedding"
    else:
        logger.warning("Ginkgo AI: unknown analysis_type '%s'", analysis_type)
        return {}

    result = _call_api("POST", path, payload)
    if result is None:
        result = {}

    _cache_put(cache_key, result)
    return result


def batch_analyze(
    sequences: list[str],
    model: str = "ginkgo-aa0-650M",
    analysis_type: str = "masked_inference",
) -> list[dict[str, Any]]:
    """Analyze multiple sequences in a batch request.

    Returns a list of result dicts (one per sequence). Individual failures
    produce empty dicts in the corresponding position.
    """
    if not sequences:
        return []

    payload: dict[str, Any] = {
        "model": model,
        "sequences": [s.strip() for s in sequences if s and s.strip()],
        "type": analysis_type,
    }

    result = _call_api("POST", "/v1/inference/batch", payload)
    if result is None:
        return [{} for _ in sequences]

    # API may return {"results": [...]} or a flat list
    if isinstance(result, list):
        return result
    if "results" in result:
        return result["results"]

    return [{} for _ in sequences]


def health_check() -> dict[str, Any]:
    """Check Ginkgo AI API connectivity and key validity.

    Returns a status dict suitable for the /health endpoint.
    """
    api_key = _get_api_key()
    if not api_key:
        return {"status": "not_configured", "message": "GINKGO_AI_API_KEY not set"}

    result = _call_api("GET", "/v1/models")
    if result is not None:
        return {"status": "connected", "models": len(result.get("models", MODELS))}
    return {
        "status": "offline",
        "message": "Could not connect to Ginkgo AI API",
    }


def _cache_put(key: str, value: dict[str, Any]) -> None:
    """Store result in cache, evicting oldest if full."""
    if len(_CACHE) >= _CACHE_MAX:
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[key] = value


def clear_cache() -> None:
    """Clear the analysis cache (useful for testing)."""
    _CACHE.clear()
