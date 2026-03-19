"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    # In production, set DATABASE_URL via env var; this default is for local dev/test only.
    database_url: str = (
        "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager"
    )
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

    # Document intake
    ocr_model: str = "Qwen/Qwen3-VL-4B-Instruct"
    extraction_model: str = "gemini-2.5-flash"
    extraction_api_key: str = ""
    openai_api_key: str = ""

    # RAG
    rag_model: str = "gemini-2.5-flash"

    # File storage
    upload_dir: str = "uploads"
    scans_dir: str = ""
    devices_dir: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
