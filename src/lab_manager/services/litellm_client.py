"""Centralized LiteLLM client with config file support.

This module provides a unified interface for LLM calls across lab-manager,
supporting multiple providers (Gemini, OpenAI, NVIDIA NIM) with optional
config file for model routing and fallbacks.

Usage:
    from lab_manager.services.litellm_client import create_completion, resolve_model_name

    response = create_completion(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Hello"}],
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any

from litellm import completion

from lab_manager.config import get_settings

logger = logging.getLogger(__name__)


def _has_value(value: Any) -> bool:
    """Return True only for non-empty strings."""
    return isinstance(value, str) and bool(value.strip())


def _first_value(*values: Any) -> str:
    """Return the first non-empty string value."""
    for value in values:
        if _has_value(value):
            return value.strip()
    return ""


def load_litellm_config() -> dict[str, Any] | None:
    """Load litellm_config.yaml if configured and exists.

    Returns None if:
    - No config path is set and default doesn't exist
    - Config file doesn't exist
    - YAML parsing fails
    """
    settings = get_settings()
    config_path = settings.litellm_config_path or "litellm_config.yaml"

    try:
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)
            logger.info("Loaded LiteLLM config from %s", config_path)
            return config
    except FileNotFoundError:
        logger.debug("LiteLLM config file not found: %s", config_path)
        return None
    except Exception as e:
        logger.error("Failed to load LiteLLM config: %s", e)
        return None


def resolve_model_name(model: str) -> str:
    """Resolve model name to LiteLLM format with provider prefix.

    Args:
        model: Model name (e.g., "gemini-2.5-flash", "gpt-4", "nvidia_nim/llama-3.2-90b")

    Returns:
        LiteLLM-compatible model name with provider prefix
    """
    if "/" in model:
        return model  # Already has provider prefix

    settings = get_settings()

    # Gemini models
    if model.startswith("gemini-"):
        return f"gemini/{model}"

    # Check for OpenAI-compatible config
    if any(
        _has_value(value)
        for value in (
            settings.rag_base_url,
            settings.rag_api_key,
            settings.openai_api_key,
            os.environ.get("RAG_BASE_URL", ""),
            os.environ.get("RAG_API_KEY", ""),
            os.environ.get("OPENAI_API_KEY", ""),
        )
    ):
        return f"openai/{model}"

    # Check for NVIDIA NIM
    if _has_value(settings.nvidia_build_api_key) or _has_value(
        os.environ.get("NVIDIA_BUILD_API_KEY", "")
    ):
        return f"nvidia_nim/{model}"

    # Default to Gemini
    return f"gemini/{model}"


def get_client_params(model: str) -> dict[str, Any]:
    """Get LiteLLM completion parameters for a model.

    This resolves the model name and fetches the appropriate API keys
    and base URLs from settings or environment variables.

    Args:
        model: Model name (with or without provider prefix)

    Returns:
        Dict with model, api_key, and optionally api_base
    """
    resolved_model = resolve_model_name(model)
    settings = get_settings()

    # NVIDIA NIM
    if resolved_model.startswith("nvidia_nim/"):
        nvidia_api_key = _first_value(
            settings.nvidia_build_api_key,
            os.environ.get("NVIDIA_BUILD_API_KEY", ""),
        )
        if not nvidia_api_key:
            raise RuntimeError(
                "No NVIDIA Build API key found. Set NVIDIA_BUILD_API_KEY."
            )
        return {
            "model": resolved_model,
            "api_key": nvidia_api_key,
            "api_base": _first_value(
                settings.rag_base_url,
                os.environ.get("RAG_BASE_URL", ""),
                os.environ.get("NVIDIA_NIM_BASE_URL", ""),
                "https://integrate.api.nvidia.com/v1",
            ),
        }

    # OpenAI-compatible (including custom endpoints)
    if resolved_model.startswith("openai/"):
        api_key = _first_value(
            settings.rag_api_key,
            settings.openai_api_key,
            os.environ.get("RAG_API_KEY", ""),
            os.environ.get("OPENAI_API_KEY", ""),
        )
        if not api_key:
            raise RuntimeError("No API key found. Set RAG_API_KEY or OPENAI_API_KEY.")
        params: dict[str, Any] = {"model": resolved_model, "api_key": api_key}
        base_url = _first_value(
            settings.rag_base_url, os.environ.get("RAG_BASE_URL", "")
        )
        if base_url:
            params["api_base"] = base_url
        return params

    # Gemini (default)
    api_key = settings.extraction_api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "No Gemini API key found. Set GEMINI_API_KEY or EXTRACTION_API_KEY."
        )
    return {"model": resolved_model, "api_key": api_key}


def create_completion(
    model: str,
    messages: list[dict],
    temperature: float = 0,
    max_tokens: int = 4096,
    **kwargs,
) -> Any:
    """Create a completion with LiteLLM.

    This is the main entry point for LLM calls. It handles model resolution,
    API key management, and optional config file routing.

    Args:
        model: Model name (e.g., "gemini-2.5-flash", "nvidia_nim/llama-3.2-90b")
        messages: List of message dicts with "role" and "content"
        temperature: Sampling temperature (0 = deterministic)
        max_tokens: Maximum tokens to generate
        **kwargs: Additional LiteLLM parameters

    Returns:
        LiteLLM completion response

    Example:
        >>> response = create_completion(
        ...     model="gemini-2.5-flash",
        ...     messages=[{"role": "user", "content": "Hello!"}],
        ... )
        >>> print(response.choices[0].message.content)
    """
    # NOTE: load_litellm_config() is available but not wired into the router.
    # If model routing/fallbacks are needed, integrate the returned config here.
    # Currently we rely on the resolved model and env vars directly.

    # Get client params (API keys, base URLs)
    client_params = get_client_params(model)

    # Merge with call params
    params = {
        **client_params,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        **kwargs,
    }

    return completion(**params)


def response_text(response: Any) -> str:
    """Extract text from a LiteLLM completion response.

    Handles both string and list content formats.

    Args:
        response: LiteLLM completion response

    Returns:
        Extracted text string
    """
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    choice = choices[0]
    content = choice.message.content
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
    return str(content).strip()
