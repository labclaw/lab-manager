"""Tests for CSV bulk import endpoints: vendors, products, inventory."""

import io

from fastapi.testclient import TestClient
from sqlmodel import Session

from lab_manager.models.location import StorageLocation


def _csv_bytes(header: str, *rows: str) -> bytes:
    """Build CSV content as UTF-8 bytes."""
    lines = [header] + list(rows)
    return "\n".join(lines).encode("utf-8")


def _csv_upload(content: bytes, filename: str = "data.csv"):
    """Return a dict suitable for TestClient file upload."""
    return {"file": (filename, io.BytesIO(content), "text/csv")}


def _create_vendor(client: TestClient, name: str = "TestVendor") -> dict:
    r = client.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_product(
    client: TestClient,
    vendor_id: int | None = None,
    name: str = "TestProduct",
    catalog: str = "CAT-001",
) -> dict:
    payload: dict = {"name": name, "catalog_number": catalog}
    if vendor_id is not None:
        payload["vendor_id"] = vendor_id
    r = client.post("/api/v1/products/", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_location(db_session: Session, name: str = "Shelf A") -> StorageLocation:
    """Insert a StorageLocation directly since no location CRUD route exists."""
    loc = StorageLocation(name=name)
    db_session.add(loc)
    db_session.commit()
    db_session.refresh(loc)
    return loc


# ---------------------------------------------------------------------------
# Vendor import
# ---------------------------------------------------------------------------


class TestImportVendors:
    """Tests for POST /api/v1/import/vendors"""

    def test_import_single_vendor(self, client):
        csv = _csv_bytes(
            "name,website,phone,email,notes",
            "BioCorp,https://biocorp.com,555-0100,sales@biocorp.com,Preferred vendor",
        )
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 1
        assert data["errors"] == []
        assert data["skipped"] == 0

    def test_import_multiple_vendors(self, client):
        csv = _csv_bytes(
            "name,website",
            "VendorA,https://a.com",
            "VendorB,https://b.com",
            "VendorC,https://c.com",
        )
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 3

    def test_import_vendors_dedup_by_name(self, client):
        _create_vendor(client, "DupVendor")
        csv = _csv_bytes("name", "DupVendor")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 0
        assert r.json()["skipped"] == 1

    def test_import_vendors_dedup_case_insensitive(self, client):
        _create_vendor(client, "CaseVendor")
        csv = _csv_bytes("name", "casevendor")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["skipped"] == 1

    def test_import_vendors_missing_name_column(self, client):
        csv = _csv_bytes("website,phone", "https://x.com,555")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "name" for e in data["errors"])

    def test_import_vendors_empty_name(self, client):
        csv = _csv_bytes("name,website", ",https://x.com")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert len(data["errors"]) >= 1

    def test_import_vendors_empty_csv(self, client):
        csv = _csv_bytes("name")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("empty" in e["message"].lower() for e in data["errors"])

    def test_import_vendors_no_header(self, client):
        csv = b""
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0

    def test_import_vendors_non_utf8(self, client):
        content = b"\x80\x81\x82\x83"
        r = client.post("/api/v1/import/vendors", files=_csv_upload(content))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("utf-8" in e["message"].lower() for e in data["errors"])

    def test_import_vendors_with_bom(self, client):
        csv = b"\xef\xbb\xbfname,website\r\nBOMVendor,https://bom.com\r\n"
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_vendors_strip_whitespace(self, client):
        csv = _csv_bytes("name,website", "  WhitespaceVendor  ,  https://ws.com  ")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_vendors_strip_excel_quote_prefix(self, client):
        csv = _csv_bytes("name", "'QuoteVendor")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_vendors_file_too_large(self, client):
        big = b"x" * (10 * 1024 * 1024 + 1)
        r = client.post("/api/v1/import/vendors", files=_csv_upload(big))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("too large" in e["message"].lower() for e in data["errors"])

    def test_import_vendors_mixed_valid_and_invalid(self, client):
        csv = _csv_bytes(
            "name,website", ",https://nope.com", "GoodVendor,https://good.com"
        )
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert len(data["errors"]) >= 1

    def test_import_vendors_mixed_valid_invalid_and_dedup(self, client):
        _create_vendor(client, "ExistingVendor")
        csv = _csv_bytes(
            "name",
            "ExistingVendor",
            ",",
            "NewVendor",
        )
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        # Row 2 (ExistingVendor) is deduped => skipped, row 3 (empty) error,
        # but errors short-circuit so imported=0 and skipped is not incremented
        # because the error row causes an early return.
        assert data["imported"] == 0
        assert len(data["errors"]) >= 1

    def test_import_vendors_all_optional_fields(self, client):
        csv = _csv_bytes(
            "name,website,phone,email,notes",
            "FullVendor,https://full.com,555-0199,info@full.com,Main supplier",
        )
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_vendors_duplicate_within_csv(self, client):
        csv = _csv_bytes("name", "SameName", "SameName")
        r = client.post("/api/v1/import/vendors", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 1
        assert data["skipped"] == 1


# ---------------------------------------------------------------------------
# Product import
# ---------------------------------------------------------------------------


class TestImportProducts:
    """Tests for POST /api/v1/import/products"""

    def test_import_single_product(self, client):
        csv = _csv_bytes("catalog_number,name,category", "CAT-100,PBS Buffer,Reagents")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 1
        assert data["errors"] == []

    def test_import_product_with_vendor_id(self, client):
        vendor = _create_vendor(client)
        csv = _csv_bytes(
            "catalog_number,name,vendor_id",
            f"CAT-200,Antibody,{vendor['id']}",
        )
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_product_invalid_vendor_id(self, client):
        csv = _csv_bytes("catalog_number,name,vendor_id", "CAT-300,BadRef,99999")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "vendor_id" for e in data["errors"])

    def test_import_products_missing_catalog_number_column(self, client):
        csv = _csv_bytes("name", "No Catalog")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "catalog_number" for e in data["errors"])

    def test_import_products_missing_name_column(self, client):
        csv = _csv_bytes("catalog_number", "CAT-400")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "name" for e in data["errors"])

    def test_import_products_missing_both_required_columns(self, client):
        csv = _csv_bytes("category", "Reagents")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        fields = {e["field"] for e in data["errors"]}
        assert "catalog_number" in fields
        assert "name" in fields

    def test_import_products_empty_catalog_number(self, client):
        csv = _csv_bytes("catalog_number,name", ",NoCatalog")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "catalog_number" for e in data["errors"])

    def test_import_products_empty_name(self, client):
        csv = _csv_bytes("catalog_number,name", "CAT-500,")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "name" for e in data["errors"])

    def test_import_products_dedup_by_catalog_and_vendor(self, client):
        vendor = _create_vendor(client, "DedupVendor")
        _create_product(client, vendor["id"], catalog="CAT-DEDUP")
        csv = _csv_bytes(
            "catalog_number,name,vendor_id",
            f"CAT-DEDUP,ProductAgain,{vendor['id']}",
        )
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["skipped"] == 1

    def test_import_products_all_fields(self, client):
        vendor = _create_vendor(client, "FullProdVendor")
        csv = _csv_bytes(
            "catalog_number,name,vendor_id,category,cas_number,storage_temp,unit,hazard_info,min_stock_level,is_hazardous,is_controlled",
            f"CAT-FULL,Full Product,{vendor['id']},Reagents,1234-56-7,-20C,mL,Flammable,10,true,false",
        )
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_products_empty_csv(self, client):
        csv = _csv_bytes("catalog_number,name")
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("empty" in e["message"].lower() for e in data["errors"])

    def test_import_products_bool_parsing(self, client):
        csv_true = _csv_bytes(
            "catalog_number,name,is_hazardous,is_controlled", "CAT-BT1,HazTrue,true,yes"
        )
        r = client.post("/api/v1/import/products", files=_csv_upload(csv_true))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

        csv_false = _csv_bytes(
            "catalog_number,name,is_hazardous,is_controlled", "CAT-BF1,HazFalse,no,0"
        )
        r = client.post("/api/v1/import/products", files=_csv_upload(csv_false))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_products_multiple_rows(self, client):
        csv = _csv_bytes(
            "catalog_number,name",
            "CAT-M1,Product M1",
            "CAT-M2,Product M2",
            "CAT-M3,Product M3",
        )
        r = client.post("/api/v1/import/products", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 3

    def test_import_products_file_too_large(self, client):
        big = b"x" * (10 * 1024 * 1024 + 1)
        r = client.post("/api/v1/import/products", files=_csv_upload(big))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("too large" in e["message"].lower() for e in data["errors"])


# ---------------------------------------------------------------------------
# Inventory import
# ---------------------------------------------------------------------------


class TestImportInventory:
    """Tests for POST /api/v1/import/inventory"""

    def _setup_product(self, client: TestClient) -> dict:
        return _create_product(client, catalog="INV-CAT-001")

    def test_import_single_inventory_item(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            f"{product['id']},100",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 1
        assert data["errors"] == []

    def test_import_inventory_with_all_fields(self, client, db_session):
        product = self._setup_product(client)
        location = _create_location(db_session, "Freezer B")
        csv = _csv_bytes(
            "product_id,quantity_on_hand,location_id,lot_number,unit,expiry_date,opened_date,status,notes,received_by",
            f"{product['id']},50,{location.id},LOT-123,mL,2026-12-31,2026-01-15,available,In good condition,Alice",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_inventory_missing_product_id_column(self, client):
        csv = _csv_bytes("quantity_on_hand", "10")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "product_id" for e in data["errors"])

    def test_import_inventory_missing_quantity_column(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes("product_id", f"{product['id']}")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "quantity_on_hand" for e in data["errors"])

    def test_import_inventory_nonexistent_product_id(self, client):
        csv = _csv_bytes("product_id,quantity_on_hand", "99999,10")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "product_id" for e in data["errors"])

    def test_import_inventory_invalid_product_id(self, client):
        csv = _csv_bytes("product_id,quantity_on_hand", "notanumber,10")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "product_id" for e in data["errors"])

    def test_import_inventory_invalid_quantity(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes("product_id,quantity_on_hand", f"{product['id']},notanumber")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "quantity_on_hand" for e in data["errors"])

    def test_import_inventory_negative_quantity(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes("product_id,quantity_on_hand", f"{product['id']},-5")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(">= 0" in e["message"] for e in data["errors"])

    def test_import_inventory_nonexistent_location_id(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,location_id",
            f"{product['id']},10,99999",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "location_id" for e in data["errors"])

    def test_import_inventory_invalid_expiry_date(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,expiry_date",
            f"{product['id']},10,not-a-date",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "expiry_date" for e in data["errors"])

    def test_import_inventory_invalid_opened_date(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,opened_date",
            f"{product['id']},10,31-12-2026",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "opened_date" for e in data["errors"])

    def test_import_inventory_invalid_status(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,status",
            f"{product['id']},10,invalid_status",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any(e["field"] == "status" for e in data["errors"])

    def test_import_inventory_valid_status_values(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand,status",
            f"{product['id']},10,opened",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_inventory_default_status_available(self, client):
        product = self._setup_product(client)
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            f"{product['id']},5",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1

    def test_import_inventory_multiple_rows(self, client):
        p1 = _create_product(client, catalog="INV-M1")
        p2 = _create_product(client, catalog="INV-M2")
        csv = _csv_bytes(
            "product_id,quantity_on_hand",
            f"{p1['id']},10",
            f"{p2['id']},20",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 2

    def test_import_inventory_empty_csv(self, client):
        csv = _csv_bytes("product_id,quantity_on_hand")
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("empty" in e["message"].lower() for e in data["errors"])

    def test_import_inventory_file_too_large(self, client):
        big = b"x" * (10 * 1024 * 1024 + 1)
        r = client.post("/api/v1/import/inventory", files=_csv_upload(big))
        assert r.status_code == 200
        data = r.json()
        assert data["imported"] == 0
        assert any("too large" in e["message"].lower() for e in data["errors"])

    def test_import_inventory_with_location(self, client, db_session):
        product = self._setup_product(client)
        location = _create_location(db_session, "Cold Room")
        csv = _csv_bytes(
            "product_id,quantity_on_hand,location_id",
            f"{product['id']},25,{location.id}",
        )
        r = client.post("/api/v1/import/inventory", files=_csv_upload(csv))
        assert r.status_code == 200
        assert r.json()["imported"] == 1


# ---------------------------------------------------------------------------
# Unit-level: helper functions from import_routes
# ---------------------------------------------------------------------------


class TestParseHelperFunctions:
    """Direct tests on _parse_csv, _strip_cell, _parse_bool, _parse_decimal,
    _parse_int, _parse_date."""

    def test_parse_csv_basic(self):
        from lab_manager.api.routes.import_routes import _parse_csv

        content = b"name,age\nAlice,30\nBob,25\n"
        rows, err = _parse_csv(content)
        assert err is None
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"

    def test_parse_csv_bom(self):
        from lab_manager.api.routes.import_routes import _parse_csv

        content = b"\xef\xbb\xbfname\nTest\n"
        rows, err = _parse_csv(content)
        assert err is None
        assert len(rows) == 1
        assert rows[0]["name"] == "Test"

    def test_parse_csv_non_utf8(self):
        from lab_manager.api.routes.import_routes import _parse_csv

        rows, err = _parse_csv(b"\xff\xfe\x00\x01")
        assert err is not None
        assert rows == []

    def test_parse_csv_empty(self):
        from lab_manager.api.routes.import_routes import _parse_csv

        rows, err = _parse_csv(b"")
        assert err is not None or rows == []

    def test_strip_cell_none(self):
        from lab_manager.api.routes.import_routes import _strip_cell

        assert _strip_cell(None) is None

    def test_strip_cell_whitespace(self):
        from lab_manager.api.routes.import_routes import _strip_cell

        assert _strip_cell("  hello  ") == "hello"

    def test_strip_cell_excel_quote(self):
        from lab_manager.api.routes.import_routes import _strip_cell

        assert _strip_cell("'=formula") == "=formula"

    def test_strip_cell_empty_string(self):
        from lab_manager.api.routes.import_routes import _strip_cell

        assert _strip_cell("   ") is None

    def test_parse_bool_true_values(self):
        from lab_manager.api.routes.import_routes import _parse_bool

        for val in ("true", "True", "TRUE", "1", "yes", "t", "T"):
            assert _parse_bool(val) is True

    def test_parse_bool_false_values(self):
        from lab_manager.api.routes.import_routes import _parse_bool

        for val in ("false", "0", "no", "f", "", None):
            assert _parse_bool(val) is False

    def test_parse_decimal_valid(self):
        from lab_manager.api.routes.import_routes import _parse_decimal

        from decimal import Decimal

        assert _parse_decimal("3.14") == Decimal("3.14")

    def test_parse_decimal_none(self):
        from lab_manager.api.routes.import_routes import _parse_decimal

        assert _parse_decimal(None) is None
        assert _parse_decimal("") is None
        assert _parse_decimal("  ") is None

    def test_parse_decimal_invalid(self):
        from lab_manager.api.routes.import_routes import _parse_decimal

        assert _parse_decimal("abc") is None

    def test_parse_int_valid(self):
        from lab_manager.api.routes.import_routes import _parse_int

        assert _parse_int("42") == 42

    def test_parse_int_none(self):
        from lab_manager.api.routes.import_routes import _parse_int

        assert _parse_int(None) is None
        assert _parse_int("") is None

    def test_parse_int_invalid(self):
        from lab_manager.api.routes.import_routes import _parse_int

        assert _parse_int("abc") is None

    def test_parse_date_valid(self):
        from lab_manager.api.routes.import_routes import _parse_date

        from datetime import date

        assert _parse_date("2026-03-27") == date(2026, 3, 27)

    def test_parse_date_none(self):
        from lab_manager.api.routes.import_routes import _parse_date

        assert _parse_date(None) is None
        assert _parse_date("") is None

    def test_parse_date_invalid(self):
        from lab_manager.api.routes.import_routes import _parse_date

        assert _parse_date("27-03-2026") is None
        assert _parse_date("not-a-date") is None
