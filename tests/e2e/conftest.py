"""E2E test fixtures and configuration.

Shared fixtures for all e2e test modules.
"""

from __future__ import annotations

import os
from typing import Generator

import httpx
import pytest
from fastapi.testclient import TestClient

# Environment keys that affect test setup
_ENV_KEYS = (
    "AUTH_ENABLED",
    "ADMIN_SECRET_KEY",
    "ADMIN_PASSWORD",
    "API_KEY",
    "SECURE_COOKIES",
)

# Admin credentials for tests
ADMIN_NAME = "E2E Test Admin"
ADMIN_EMAIL = "e2e-admin@test.local"
ADMIN_PASSWORD = "e2e-test-password-secure-12345"


@pytest.fixture(scope="session")
def e2e_client() -> Generator[TestClient | httpx.Client, None, None]:
    """Session-scoped HTTP client for e2e tests.

    Uses httpx against APP_BASE_URL if set, otherwise creates a local
    TestClient with auth enabled + SQLite.
    """
    base_url = os.environ.get("APP_BASE_URL")
    if base_url:
        client = httpx.Client(base_url=base_url, timeout=30, follow_redirects=True)
        yield client
        client.close()
        return

    # Save originals for restoration
    orig_env = {k: os.environ.get(k) for k in _ENV_KEYS}

    # Configure test environment
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "e2e-test-secret-key-12345"
    os.environ["ADMIN_PASSWORD"] = ADMIN_PASSWORD
    os.environ["API_KEY"] = "e2e-test-api-key"
    os.environ["SECURE_COOKIES"] = "false"

    # Import after env vars are set
    from lab_manager.config import get_settings

    get_settings.cache_clear()

    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Import models to register them
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Override database
    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.database import get_db

    app = create_app()

    def override_get_db():
        with Session(engine) as session:
            yield session
            session.commit()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        engine.dispose()
        db_module._engine = original_engine
        db_module._session_factory = original_factory
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


@pytest.fixture(scope="session")
def authenticated_client(
    e2e_client: TestClient | httpx.Client,
) -> TestClient | httpx.Client:
    """Client that is already logged in as admin.

    Performs setup if needed and logs in.
    """
    # Check setup status
    status_resp = e2e_client.get("/api/setup/status")
    needs_setup = status_resp.json().get("needs_setup", False)

    if needs_setup:
        # Complete setup
        e2e_client.post(
            "/api/setup/complete",
            json={
                "admin_name": ADMIN_NAME,
                "admin_email": ADMIN_EMAIL,
                "admin_password": ADMIN_PASSWORD,
            },
        )

    # Login
    login_resp = e2e_client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"

    return e2e_client


@pytest.fixture(scope="session")
def test_vendor_id(authenticated_client: TestClient | httpx.Client) -> int:
    """Create a test vendor and return its ID."""
    resp = authenticated_client.post(
        "/api/v1/vendors/",
        json={
            "name": "E2E Test Vendor",
            "email": "vendor@e2e-test.local",
            "website": "https://e2e-test.local",
        },
    )
    assert resp.status_code == 201, f"Failed to create vendor: {resp.text}"
    return resp.json()["id"]


@pytest.fixture(scope="session")
def test_product_id(
    authenticated_client: TestClient | httpx.Client,
    test_vendor_id: int,
) -> int:
    """Create a test product and return its ID."""
    resp = authenticated_client.post(
        "/api/v1/products/",
        json={
            "catalog_number": "E2E-TEST-001",
            "name": "E2E Test Product",
            "vendor_id": test_vendor_id,
            "category": "Reagents",
            "unit_price": 99.99,
        },
    )
    assert resp.status_code == 201, f"Failed to create product: {resp.text}"
    return resp.json()["id"]


@pytest.fixture(scope="session")
def test_order_id(
    authenticated_client: TestClient | httpx.Client,
    test_vendor_id: int,
) -> int:
    """Create a test order and return its ID."""
    resp = authenticated_client.post(
        "/api/v1/orders/",
        json={
            "po_number": "E2E-PO-001",
            "vendor_id": test_vendor_id,
            "status": "pending",
        },
    )
    assert resp.status_code == 201, f"Failed to create order: {resp.text}"
    data = resp.json()
    return data.get("order", data)["id"]


@pytest.fixture(scope="session")
def test_equipment_id(authenticated_client: TestClient | httpx.Client) -> int:
    """Create test equipment and return its ID."""
    resp = authenticated_client.post(
        "/api/v1/equipment/",
        json={
            "name": "E2E Test Equipment",
            "model": "TEST-MODEL-001",
            "serial_number": "SN-E2E-001",
            "status": "active",
            "location": "Lab A",
        },
    )
    assert resp.status_code == 201, f"Failed to create equipment: {resp.text}"
    return resp.json()["id"]


@pytest.fixture(scope="session")
def test_inventory_id(
    authenticated_client: TestClient | httpx.Client,
    test_product_id: int,
) -> int:
    """Create test inventory item and return its ID."""
    resp = authenticated_client.post(
        "/api/v1/inventory/",
        json={
            "product_id": test_product_id,
            "quantity": 100,
            "location": "Shelf A1",
            "lot_number": "LOT-E2E-001",
        },
    )
    assert resp.status_code == 201, f"Failed to create inventory: {resp.text}"
    return resp.json()["id"]
