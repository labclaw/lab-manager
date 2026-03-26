"""Application settings loaded from environment variables."""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application configuration."""

    # Default DATABASE_URL for local dev/test. Override in production via env.
    database_url: str = (
        "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager"
    )

    @model_validator(mode="after")
    def _warn_default_database_url(self):
        """Log a warning if the default DATABASE_URL is still in use."""
        if self.database_url and "labmanager:labmanager@localhost" in self.database_url:
            logger.warning(
                "Using default DATABASE_URL (localhost). "
                "Set DATABASE_URL explicitly for production deployments."
            )
        return self

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

    @model_validator(mode="after")
    def _warn_default_admin_password(self):
        """Warn when ADMIN_PASSWORD is empty or a known default."""
        if self.auth_enabled:
            pw = self.admin_password.strip()
            if not pw:
                logger.warning(
                    "ADMIN_PASSWORD is empty — the admin panel will be unprotected. "
                    "Set ADMIN_PASSWORD to a strong value."
                )
            elif pw.startswith("changeme"):
                logger.warning(
                    "ADMIN_PASSWORD is still a default value (%s). "
                    "Change it to a strong password before deploying.",
                    pw,
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
    secure_cookies: bool = False

    # Document intake — OCR tiered detection
    # ocr_tier: "local" (vLLM only), "api" (cloud APIs), "auto" (local first, API fallback)
    ocr_tier: str = "auto"
    # OCR model: benchmark winner — llama-3.2-90b 100% success on sample documents
    ocr_model: str = "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
    # Local OCR default: dots.mocr 3B — open-source Elo #1 (1124.7)
    ocr_local_model: str = "dots_mocr"  # provider name from OCR_PROVIDERS registry
    ocr_local_url: str = "http://localhost:8000/v1"  # vLLM endpoint for local models
    # Extraction model: GLM-5 82.4% success, 0.92 avg confidence on sample documents
    extraction_model: str = "nvidia_nim/z-ai/glm5"
    extraction_api_key: str = ""
    mistral_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    google_api_key: str = ""

    # RAG — uses NVIDIA API when nvidia_build_api_key is set
    rag_model: str = "nvidia_nim/z-ai/glm5"
    rag_api_key: str = ""
    rag_base_url: str = ""
    nvidia_build_api_key: str = ""

    # LiteLLM — optional config file for model routing/fallbacks
    litellm_config_path: str = ""  # Path to litellm_config.yaml (empty = disabled)

    # Document routing — cost-aware model selection (inspired by OpenClaw)
    # "auto" = score-based routing, "low"/"medium"/"high" = force tier
    routing_strategy: str = "auto"

    # Proactive notifications — push alerts to external channels
    slack_webhook_url: str = ""  # Slack incoming webhook URL
    notification_webhook_url: str = ""  # Generic HTTP webhook URL
    notification_severities: str = "critical,warning"  # Comma-separated

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
