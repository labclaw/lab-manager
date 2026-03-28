"""Test auth guards on documents, inventory, and equipment GET endpoints."""

import pytest

from lab_manager.config import get_settings


@pytest.fixture(autouse=True)
def _enable_auth(monkeypatch):
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


class TestDocumentsAuthRequired:
    def test_list_documents_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/documents/")
        assert resp.status_code == 401

    def test_get_document_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/documents/1")
        assert resp.status_code == 401

    def test_document_stats_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/documents/stats")
        assert resp.status_code == 401


class TestInventoryAuthRequired:
    def test_list_inventory_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/inventory/")
        assert resp.status_code == 401

    def test_low_stock_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/inventory/low-stock")
        assert resp.status_code == 401

    def test_expiring_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/inventory/expiring")
        assert resp.status_code == 401

    def test_get_item_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/inventory/1")
        assert resp.status_code == 401

    def test_item_history_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/inventory/1/history")
        assert resp.status_code == 401


class TestEquipmentAuthRequired:
    def test_list_equipment_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/equipment/")
        assert resp.status_code == 401

    def test_get_equipment_requires_auth(self, auth_client):
        resp = auth_client.get("/api/v1/equipment/1")
        assert resp.status_code == 401
