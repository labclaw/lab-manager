"""Test orders route auth guards — all GET endpoints require view_orders permission."""

import pytest

from lab_manager.config import get_settings


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
    """Enable auth for these tests."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret-key-for-signing")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password-12345")
    monkeypatch.setenv("API_KEY", "test-api-key-12345")
    monkeypatch.setenv("SECURE_COOKIES", "false")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("AUTH_ENABLED", raising=False)
    get_settings.cache_clear()


@pytest.fixture
def auth_client(db_session):
    """TestClient with auth enabled, using the shared test DB."""
    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    from starlette.testclient import TestClient

    with TestClient(app) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory


class TestOrdersAuthRequired:
    """All order GET endpoints must return 401 when auth is enabled and no credentials provided."""

    def test_list_orders_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/orders/")
        assert resp.status_code == 401

    def test_get_order_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/orders/1")
        assert resp.status_code == 401

    def test_list_order_items_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/orders/1/items")
        assert resp.status_code == 401

    def test_get_order_item_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/orders/1/items/1")
        assert resp.status_code == 401
