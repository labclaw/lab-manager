"""E2E tests for CSV import endpoints.

Tests CSV import for vendors, products, and inventory via multipart upload.
"""

from __future__ import annotations

import io
import httpx
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4


def _make_csv(headers: list[str], rows: list[list[str]]) -> bytes:
    """Build a CSV bytes buffer from headers and rows."""
    buf = io.BytesIO()
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    buf.write("\n".join(lines).encode("utf-8"))
    buf.seek(0)
    return buf.getvalue()


@pytest.mark.e2e
class TestImportVendors:
    """E2E tests for vendor CSV import."""

    def test_import_vendors_basic(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST /api/v1/import/vendors with valid CSV creates vendors."""
        suffix = uuid4().hex[:8]
        csv_data = _make_csv(
            ["name", "email", "website"],
            [
                [
                    f"E2E Import Vendor {suffix}",
                    f"import-{suffix}@test.local",
                    "https://test.local",
                ],
            ],
        )
        resp = authenticated_client.post(
            "/api/v1/import/vendors",
            files={"file": ("vendors.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "imported" in data
        assert data["imported"] >= 1

    def test_import_vendors_multiple_rows(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Import multiple vendors in one CSV."""
        suffix = uuid4().hex[:8]
        csv_data = _make_csv(
            ["name"],
            [
                [f"E2E Bulk Vendor A {suffix}"],
                [f"E2E Bulk Vendor B {suffix}"],
                [f"E2E Bulk Vendor C {suffix}"],
            ],
        )
        resp = authenticated_client.post(
            "/api/v1/import/vendors",
            files={"file": ("vendors.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["imported"] >= 1

    def test_import_vendors_duplicate_skipped(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Duplicate vendor names are skipped."""
        suffix = uuid4().hex[:8]
        name = f"E2E Dup Vendor {suffix}"
        csv_data = _make_csv(["name"], [[name], [name]])
        resp = authenticated_client.post(
            "/api/v1/import/vendors",
            files={"file": ("vendors.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["imported"] >= 1
        assert data.get("skipped", 0) >= 1

    def test_import_vendors_missing_name(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """CSV missing required 'name' column returns errors."""
        csv_data = _make_csv(["email"], [["no-name@test.local"]])
        resp = authenticated_client.post(
            "/api/v1/import/vendors",
            files={"file": ("vendors.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201, 422)
        if resp.status_code in (200, 201):
            data = resp.json()
            assert len(data.get("errors", [])) > 0

    def test_import_vendors_empty_file(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Empty CSV returns error or zero imported."""
        csv_data = b"name\n"
        resp = authenticated_client.post(
            "/api/v1/import/vendors",
            files={"file": ("vendors.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201, 422)
        if resp.status_code in (200, 201):
            assert resp.json()["imported"] == 0

    def test_import_vendors_no_file(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST without file field returns 422."""
        resp = authenticated_client.post("/api/v1/import/vendors")
        assert resp.status_code == 422


@pytest.mark.e2e
class TestImportProducts:
    """E2E tests for product CSV import."""

    def test_import_products_basic(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_vendor_id: int,
    ):
        """POST /api/v1/import/products with valid CSV creates products."""
        suffix = uuid4().hex[:8]
        csv_data = _make_csv(
            ["catalog_number", "name", "vendor_id"],
            [
                [
                    f"E2E-IMP-{suffix}",
                    f"E2E Import Product {suffix}",
                    str(test_vendor_id),
                ],
            ],
        )
        resp = authenticated_client.post(
            "/api/v1/import/products",
            files={"file": ("products.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["imported"] >= 1

    def test_import_products_invalid_vendor(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Product with non-existent vendor_id returns row error."""
        suffix = uuid4().hex[:8]
        csv_data = _make_csv(
            ["catalog_number", "name", "vendor_id"],
            [
                [f"E2E-BADVN-{suffix}", f"Bad Vendor Product {suffix}", "999999"],
            ],
        )
        resp = authenticated_client.post(
            "/api/v1/import/products",
            files={"file": ("products.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201, 422)
        if resp.status_code in (200, 201):
            data = resp.json()
            assert len(data.get("errors", [])) > 0

    def test_import_products_missing_required(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """CSV missing catalog_number returns errors."""
        csv_data = _make_csv(["name"], [["Some Product"]])
        resp = authenticated_client.post(
            "/api/v1/import/products",
            files={"file": ("products.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201, 422)
        if resp.status_code in (200, 201):
            data = resp.json()
            assert len(data.get("errors", [])) > 0


@pytest.mark.e2e
class TestImportInventory:
    """E2E tests for inventory CSV import."""

    def test_import_inventory_basic(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """POST /api/v1/import/inventory with valid CSV creates inventory."""
        csv_data = _make_csv(
            ["product_id", "quantity_on_hand"],
            [
                [str(test_product_id), "100"],
            ],
        )
        resp = authenticated_client.post(
            "/api/v1/import/inventory",
            files={"file": ("inventory.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["imported"] >= 1

    def test_import_inventory_with_all_fields(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """Import inventory with optional fields."""
        suffix = uuid4().hex[:8]
        csv_data = _make_csv(
            [
                "product_id",
                "quantity_on_hand",
                "lot_number",
                "expiry_date",
                "location",
                "notes",
            ],
            [
                [
                    str(test_product_id),
                    "50",
                    f"LOT-IMP-{suffix}",
                    "2027-12-31",
                    "Shelf D1",
                    "E2E imported",
                ],
            ],
        )
        resp = authenticated_client.post(
            "/api/v1/import/inventory",
            files={"file": ("inventory.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["imported"] >= 1

    def test_import_inventory_invalid_product(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Inventory with non-existent product_id returns row error."""
        csv_data = _make_csv(
            ["product_id", "quantity_on_hand"],
            [["999999", "10"]],
        )
        resp = authenticated_client.post(
            "/api/v1/import/inventory",
            files={"file": ("inventory.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201, 422)
        if resp.status_code in (200, 201):
            data = resp.json()
            assert len(data.get("errors", [])) > 0

    def test_import_inventory_negative_quantity(
        self,
        authenticated_client: TestClient | httpx.Client,
        test_product_id: int,
    ):
        """Negative quantity_on_hand should return row error."""
        csv_data = _make_csv(
            ["product_id", "quantity_on_hand"],
            [[str(test_product_id), "-5"]],
        )
        resp = authenticated_client.post(
            "/api/v1/import/inventory",
            files={"file": ("inventory.csv", csv_data, "text/csv")},
        )
        assert resp.status_code in (200, 201, 422)
        if resp.status_code in (200, 201):
            data = resp.json()
            # Negative qty should be flagged
            assert data["imported"] == 0 or len(data.get("errors", [])) > 0

    def test_import_inventory_no_file(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """POST without file returns 422."""
        resp = authenticated_client.post("/api/v1/import/inventory")
        assert resp.status_code == 422
