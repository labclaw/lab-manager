"""Shared test fixtures."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["MEILISEARCH_URL"] = "http://localhost:7700"
os.environ["AUTH_ENABLED"] = "false"

from lab_manager.config import get_settings

get_settings.cache_clear()


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401 — register all models with metadata

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(db_session):
    # Ensure auth is disabled for standard tests (test_auth.py manages its own).
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
