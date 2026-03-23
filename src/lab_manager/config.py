"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    # In production, set DATABASE_URL via env var; this default is for local dev/test only.
    database_url: str = (
        "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager"
    )

    @model_validator(mode="after")
    def _normalize_database_urls(self):
        """Ensure SQLAlchemy dialect prefix for managed DB providers (e.g. DO App Platform)."""
        for attr in ("database_url", "database_readonly_url"):
            val = getattr(self, attr)
            if val and val.startswith("postgresql://"):
                object.__setattr__(
                    self, attr, val.replace("postgresql://", "postgresql+psycopg://", 1)
                )
        return self

    @model_validator(mode="after")
    def _validate_auth_config(self):
        """Ensure ADMIN_SECRET_KEY is set when auth is enabled."""
        if self.auth_enabled and not self.admin_secret_key:
            raise ValueError(
                "ADMIN_SECRET_KEY must be set when AUTH_ENABLED=true. "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return self

    meilisearch_url: str = "http://localhost:7700"
    meilisearch_api_key: str = ""

    # Read-only DB for RAG queries (falls back to main engine + SET TRANSACTION READ ONLY)
    database_readonly_url: str = ""

    # Lab identity (configurable per deployment)
    lab_name: str = "My Lab"
    lab_subtitle: str = ""

    # Auth
    api_key: str = ""
    admin_secret_key: str = ""
    admin_password: str = ""
    auth_enabled: bool = True
    secure_cookies: bool = True

    # Document intake — OCR tiered detection
    # ocr_tier: "local" (vLLM only), "api" (cloud APIs), "auto" (local first, API fallback)
    ocr_tier: str = "auto"
    # OCR model: benchmark winner — llama-3.2-90b 100% success on 279 Shen Lab docs
    ocr_model: str = "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
    ocr_local_model: str = "deepseek_ocr"  # provider name from OCR_PROVIDERS registry
    ocr_local_url: str = "http://localhost:8000/v1"  # vLLM endpoint for local models
    # Extraction model: GLM-5 82.4% success, 0.92 avg confidence on 279 docs
    extraction_model: str = "nvidia_nim/z-ai/glm5"
    extraction_api_key: str = ""
    mistral_api_key: str = ""
    openai_api_key: str = ""

    # RAG — uses NVIDIA API when nvidia_build_api_key is set
    rag_model: str = "nvidia_nim/z-ai/glm5"
    rag_api_key: str = ""
    rag_base_url: str = ""
    nvidia_build_api_key: str = ""

    # LiteLLM — optional config file for model routing/fallbacks
    litellm_config_path: str = ""  # Path to litellm_config.yaml (empty = disabled)

    # Logging
    log_format: str = "console"  # "console" or "json"

    # File storage
    upload_dir: str = "uploads"
    scans_dir: str = ""
    devices_dir: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
