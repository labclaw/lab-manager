"""Tests for CSV bulk import endpoints."""

import io


def _csv_bytes(header: str, *rows: str) -> bytes:
    """Build CSV content from header + rows."""
    lines = [header] + list(rows)
    return "\n".join(lines).encode("utf-8")


def _upload(client, entity: str, content: bytes, filename: str = "test.csv"):
    """POST a CSV file to the import endpoint."""
    return client.post(
        f"/api/v1/import/{entity}",
        files={"file": (filename, io.BytesIO(content), "text/csv")},
    )


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


class TestImportVendors:
    def test_valid_csv(self, client):
        csv = _csv_bytes(
            "name,website,phone,email,notes",
            "Sigma-Aldrich,https://sigma.com,555-0100,info@sigma.com,chemicals",
            "Fisher Scientific,https://fisher.com,555-0200,,",
        )
        resp = _upload(client, "vendors", csv)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["errors"] == []
        assert data["skipped"] == 0

    def test_missing_required_column(self, client):
        csv = _csv_bytes("website,phone", "https://example.com,555-0001")
        resp = _upload(client, "vendors", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any(e["field"] == "name" for e in data["errors"])

    def test_missing_name_value(self, client):
        csv = _csv_bytes("name,website", ",https://example.com")
        resp = _upload(client, "vendors", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any(
            e["field"] == "name" and "required" in e["message"] for e in data["errors"]
        )

    def test_duplicate_vendor_skipped(self, client):
        csv = _csv_bytes("name", "TestVendor")
        # First import
        resp1 = _upload(client, "vendors", csv)
        assert resp1.json()["imported"] == 1
        # Second import — same name should be skipped
        resp2 = _upload(client, "vendors", csv)
        data2 = resp2.json()
        assert data2["imported"] == 0
        assert data2["skipped"] == 1
        assert data2["errors"] == []

    def test_empty_csv(self, client):
        csv = _csv_bytes("name")  # header only, no rows
        resp = _upload(client, "vendors", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("empty" in e["message"] for e in data["errors"])


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


class TestImportProducts:
    def _make_vendor(self, client):
        csv = _csv_bytes("name", "TestVendor")
        resp = _upload(client, "vendors", csv)
        assert resp.json()["imported"] == 1

    def test_valid_csv(self, client):
        self._make_vendor(client)
        csv = _csv_bytes(
            "catalog_number,name,vendor_id,category,unit",
            "ABC-123,Test Reagent,1,Chemicals,mL",
        )
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 1
        assert data["errors"] == []

    def test_missing_required_fields(self, client):
        csv = _csv_bytes("category,unit", "Chemicals,mL")
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 0
        fields = {e["field"] for e in data["errors"]}
        assert "catalog_number" in fields or "name" in fields

    def test_invalid_vendor_id(self, client):
        csv = _csv_bytes(
            "catalog_number,name,vendor_id",
            "XYZ-999,Bad Product,9999",
        )
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("vendor_id" in e["field"] for e in data["errors"])

    def test_duplicate_product_skipped(self, client):
        csv = _csv_bytes("catalog_number,name", "DUP-001,Dup Product")
        resp1 = _upload(client, "products", csv)
        assert resp1.json()["imported"] == 1
        resp2 = _upload(client, "products", csv)
        data2 = resp2.json()
        assert data2["imported"] == 0
        assert data2["skipped"] == 1

    def test_boolean_fields(self, client):
        csv = _csv_bytes(
            "catalog_number,name,is_hazardous,is_controlled",
            "HAZ-001,Hazardous Thing,true,false",
            "HAZ-002,Controlled Thing,0,1",
        )
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 2


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


class TestImportInventory:
    def _make_product(self, client):
        csv = _csv_bytes("catalog_number,name", "INV-001,Inventory Product")
        resp = _upload(client, "products", csv)
        assert resp.json()["imported"] == 1

    def test_valid_csv(self, client):
        self._make_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,lot_number,unit,status",
            "1,10.5,LOT-A,mL,available",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 1
        assert data["errors"] == []

    def test_missing_product_id(self, client):
        csv = _csv_bytes(
            "quantity_on_hand,unit",
            "5,mL",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("product_id" in e["field"] for e in data["errors"])

    def test_invalid_product_id(self, client):
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            "9999,10",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("does not exist" in e["message"] for e in data["errors"])

    def test_negative_quantity(self, client):
        self._make_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            "1,-5",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("must be >= 0" in e["message"] for e in data["errors"])

    def test_invalid_date_format(self, client):
        self._make_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,expiry_date",
            "1,10,not-a-date",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("YYYY-MM-DD" in e["message"] for e in data["errors"])

    def test_valid_date(self, client):
        self._make_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,expiry_date,status",
            "1,10,2026-12-31,available",
        )
        resp = _upload(client, "inventory", csv)
        assert resp.json()["imported"] == 1

    def test_invalid_status(self, client):
        self._make_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,status",
            "1,10,bogus",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 0
        assert any("status" in e["field"] for e in data["errors"])


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestImportEdgeCases:
    def test_bom_handling(self, client):
        """UTF-8 BOM prefix should be handled gracefully."""
        content = b"\xef\xbb\xbf" + _csv_bytes("name", "BOM Vendor")
        resp = _upload(client, "vendors", content)
        assert resp.json()["imported"] == 1

    def test_excel_injection_stripped(self, client):
        """Single-quote prefix from export should be stripped."""
        csv = _csv_bytes("name,website", "'SafeVendor,https://safe.com")
        resp = _upload(client, "vendors", csv)
        data = resp.json()
        assert data["imported"] == 1


class TestImportPartialSuccess:
    """Valid rows must be imported even when other rows have errors."""

    def test_vendors_partial_success(self, client):
        csv = _csv_bytes(
            "name,website",
            "GoodVendor,https://good.com",
            ",",  # row 3: empty name -> error
            "AnotherGood,https://another.com",
        )
        resp = _upload(client, "vendors", csv)
        data = resp.json()
        assert data["imported"] == 2
        assert len(data["errors"]) >= 1
        assert any("required" in e["message"] for e in data["errors"])

    def test_products_partial_success(self, client):
        _upload(client, "vendors", _csv_bytes("name", "TestVendor"))
        csv = _csv_bytes(
            "catalog_number,name,vendor_id",
            "GOOD-001,Good Product,1",
            ",Bad Product,1",  # missing catalog_number
            "GOOD-002,Another Good,1",
        )
        resp = _upload(client, "products", csv)
        data = resp.json()
        assert data["imported"] == 2
        assert len(data["errors"]) >= 1

    def test_inventory_partial_success(self, client):
        _upload(
            client, "products", _csv_bytes("catalog_number,name", "INV-PS,PS Product")
        )
        csv = _csv_bytes(
            "product_id,quantity_on_hand,status",
            "1,5,available",
            "9999,10,available",  # bad product_id
            "1,3,available",
        )
        resp = _upload(client, "inventory", csv)
        data = resp.json()
        assert data["imported"] == 2
        assert len(data["errors"]) >= 1
