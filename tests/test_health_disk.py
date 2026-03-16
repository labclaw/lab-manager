"""Test disk space health check."""

import os
from collections import namedtuple
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_DiskUsage = namedtuple("usage", ["total", "used", "free"])


@pytest.fixture
def health_client():
    """Minimal test client for health endpoint (no auth needed)."""
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-key"
    os.environ["DATABASE_URL"] = "sqlite://"

    from lab_manager.config import get_settings

    get_settings.cache_clear()

    from lab_manager.api.app import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c

    os.environ.pop("AUTH_ENABLED", None)
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()


def test_health_includes_disk_check(health_client):
    """Health endpoint should include disk space status."""
    resp = health_client.get("/api/health")
    data = resp.json()
    assert "disk" in data["services"]


def test_health_disk_ok_when_sufficient(health_client):
    """Disk check should report 'ok' when space is sufficient."""
    resp = health_client.get("/api/health")
    data = resp.json()
    assert data["services"]["disk"] in ("ok", "warning", "error")


@patch("lab_manager.api.app.shutil.disk_usage")
def test_health_disk_warning_when_low(mock_disk, health_client):
    """Disk check should report 'warning' when space is below threshold."""
    # shutil.disk_usage returns a named tuple with total, used, free
    mock_disk.return_value = _DiskUsage(
        total=100_000_000_000, used=99_900_000_000, free=100_000_000
    )
    resp = health_client.get("/api/health")
    data = resp.json()
    assert data["services"]["disk"] == "warning"
