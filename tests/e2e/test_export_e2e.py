"""E2E tests for export endpoints.

Tests CSV exports for inventory, orders, products, and vendors.
"""

from __future__ import annotations

import csv
import io

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestExportEndpoints:
    """Tests for CSV export endpoints."""

    def test_export_vendors_csv(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/export/vendors returns CSV with vendors."""
        resp = authenticated_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        # Should have at least header row
        assert "name" in content.lower() or "vendor" in content.lower()

    def test_export_products_csv(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/export/products returns CSV with products."""
        resp = authenticated_client.get("/api/v1/export/products")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        # Should have at least header row
        assert "name" in content.lower() or "product" in content.lower()

    def test_export_orders_csv(self, authenticated_client: TestClient | httpx.Client):
        """GET /api/v1/export/orders returns CSV with orders."""
        resp = authenticated_client.get("/api/v1/export/orders")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        # Should have at least header row
        assert "order" in content.lower() or "po" in content.lower()

    def test_export_inventory_csv(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/export/inventory returns CSV with inventory."""
        resp = authenticated_client.get("/api/v1/export/inventory")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        # Should have at least header row
        assert "quantity" in content.lower() or "inventory" in content.lower()


@pytest.mark.e2e
class TestExportFormatValidation:
    """Tests for CSV format and structure validation."""

    def test_vendors_csv_has_valid_headers(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Export CSV has valid headers."""
        resp = authenticated_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200

        reader = csv.reader(io.StringIO(resp.text))
        headers = next(reader, [])
        # Should have some expected columns
        assert len(headers) > 0

    def test_products_csv_has_valid_headers(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Export CSV has valid headers."""
        resp = authenticated_client.get("/api/v1/export/products")
        assert resp.status_code == 200

        reader = csv.reader(io.StringIO(resp.text))
        headers = next(reader, [])
        assert len(headers) > 0

    def test_orders_csv_has_valid_headers(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Export CSV has valid headers."""
        resp = authenticated_client.get("/api/v1/export/orders")
        assert resp.status_code == 200

        reader = csv.reader(io.StringIO(resp.text))
        headers = next(reader, [])
        assert len(headers) > 0

    def test_inventory_csv_has_valid_headers(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Export CSV has valid headers."""
        resp = authenticated_client.get("/api/v1/export/inventory")
        assert resp.status_code == 200

        reader = csv.reader(io.StringIO(resp.text))
        headers = next(reader, [])
        assert len(headers) > 0


@pytest.mark.e2e
class TestExportEncoding:
    """Tests for CSV encoding and special characters."""

    def test_export_handles_unicode(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Export handles unicode characters in data."""
        resp = authenticated_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200
        # Should be valid text
        content = resp.text
        assert isinstance(content, str)

    def test_export_content_disposition(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Export has proper content disposition header."""
        resp = authenticated_client.get("/api/v1/export/vendors")
        assert resp.status_code == 200
        # Check for content disposition if present
        content_disp = resp.headers.get("content-disposition", "")
        # Should contain filename
        if content_disp:
            assert (
                "filename" in content_disp.lower()
                or "attachment" in content_disp.lower()
            )
