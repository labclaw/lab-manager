"""E2E tests for analytics endpoints.

Tests all analytics dashboard, spending, inventory value, and reporting.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestAnalyticsDashboard:
    """Tests for analytics dashboard endpoints."""

    def test_dashboard(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/dashboard returns summary stats."""
        resp = authenticated_client.get("/api/v1/analytics/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_products" in data
        assert "total_vendors" in data
        assert "total_orders" in data

    def test_documents_stats(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/documents/stats returns doc stats."""
        resp = authenticated_client.get("/api/v1/analytics/documents/stats")
        assert resp.status_code in (200, 404)  # May be merged into dashboard
        if resp.status_code == 200:
            data = resp.json()
            # Stats should include some counts
            assert isinstance(data, dict)


@pytest.mark.e2e
class TestSpendingAnalytics:
    """Tests for spending analytics endpoints."""

    def test_spending_overview(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/spending returns spending summary."""
        resp = authenticated_client.get("/api/v1/analytics/spending")
        assert resp.status_code == 200
        data = resp.json()
        # Should include total spending
        assert isinstance(data, dict)

    def test_spending_by_vendor(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/spending/by-vendor returns vendor breakdown."""
        resp = authenticated_client.get("/api/v1/analytics/spending/by-vendor")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    def test_spending_by_month(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/spending/by-month returns monthly breakdown."""
        resp = authenticated_client.get("/api/v1/analytics/spending/by-month")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    def test_vendor_summary(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """GET /api/v1/analytics/vendors/{id}/summary returns vendor stats."""
        resp = authenticated_client.get(
            f"/api/v1/analytics/vendors/{test_vendor_id}/summary"
        )
        assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestInventoryAnalytics:
    """Tests for inventory analytics endpoints."""

    def test_inventory_value(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/inventory/value returns total inventory value."""
        resp = authenticated_client.get("/api/v1/analytics/inventory/value")
        assert resp.status_code == 200
        data = resp.json()
        # Should include total value
        assert isinstance(data, dict)

    def test_inventory_report(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/inventory/report returns detailed report."""
        resp = authenticated_client.get("/api/v1/analytics/inventory/report")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, dict)


@pytest.mark.e2e
class TestProductAnalytics:
    """Tests for product analytics endpoints."""

    def test_top_products(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/products/top returns top ordered products."""
        resp = authenticated_client.get("/api/v1/analytics/products/top")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))


@pytest.mark.e2e
class TestOrderAnalytics:
    """Tests for order analytics endpoints."""

    def test_orders_history(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/orders/history returns order history."""
        resp = authenticated_client.get("/api/v1/analytics/orders/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))


@pytest.mark.e2e
class TestStaffAnalytics:
    """Tests for staff activity analytics."""

    def test_staff_activity(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/analytics/staff/activity returns staff activity."""
        resp = authenticated_client.get("/api/v1/analytics/staff/activity")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, (list, dict))


@pytest.mark.e2e
class TestAnalyticsFiltering:
    """Tests for analytics filtering and date ranges."""

    def test_spending_with_date_range(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET spending with date range filter."""
        resp = authenticated_client.get(
            "/api/v1/analytics/spending",
            params={"start_date": "2024-01-01", "end_date": "2024-12-31"},
        )
        assert resp.status_code == 200

    def test_orders_history_with_limit(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET orders history with limit."""
        resp = authenticated_client.get(
            "/api/v1/analytics/orders/history",
            params={"limit": 10},
        )
        assert resp.status_code == 200

    def test_top_products_with_limit(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET top products with limit."""
        resp = authenticated_client.get(
            "/api/v1/analytics/products/top",
            params={"limit": 5},
        )
        assert resp.status_code == 200
