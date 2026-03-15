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

    # Auth
    api_key: str = ""
    admin_secret_key: str = ""
    auth_enabled: bool = False

    # Document intake
    ocr_model: str = "Qwen/Qwen3-VL-4B-Instruct"
    extraction_model: str = "gemini-3.1-flash-preview"
    extraction_api_key: str = ""

    # File storage
    upload_dir: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
