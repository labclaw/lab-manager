"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration."""

    database_url: str = (
        "postgresql+psycopg://labmanager:labmanager@localhost:5432/labmanager"
    )
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_api_key: str = ""

    # Document intake
    ocr_model: str = "Qwen/Qwen3-VL-4B-Instruct"
    extraction_model: str = "gemini-2.5-flash-preview"
    extraction_api_key: str = ""
    auto_approve_threshold: float = 0.95

    # File storage
    upload_dir: str = "uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
