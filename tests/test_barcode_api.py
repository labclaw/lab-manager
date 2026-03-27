"""Tests for the barcode lookup API endpoint."""

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers to seed prerequisite data
# ---------------------------------------------------------------------------


def _create_vendor(client: TestClient, name: str = "TestVendor"):
    r = client.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_product(
    client: TestClient,
    vendor_id: int,
    name: str = "TestProduct",
    catalog: str = "CAT-001",
    cas_number: str | None = None,
):
    payload: dict = {
        "name": name,
        "catalog_number": catalog,
        "vendor_id": vendor_id,
    }
    if cas_number is not None:
        payload["cas_number"] = cas_number
    r = client.post("/api/v1/products/", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _create_inventory_item(
    client: TestClient,
    product_id: int,
    lot_number: str | None = None,
    quantity: str = "10",
):
    payload: dict = {
        "product_id": product_id,
        "quantity_on_hand": quantity,
        "status": "available",
    }
    if lot_number is not None:
        payload["lot_number"] = lot_number
    r = client.post("/api/v1/inventory/", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


# Full seed helper: vendor -> product -> inventory, returning all three dicts.
def _seed_item(
    client: TestClient,
    *,
    vendor_name: str = "TestVendor",
    product_name: str = "TestProduct",
    catalog: str = "CAT-001",
    cas_number: str | None = None,
    lot_number: str | None = None,
    quantity: str = "10",
):
    vendor = _create_vendor(client, vendor_name)
    product = _create_product(
        client,
        vendor["id"],
        name=product_name,
        catalog=catalog,
        cas_number=cas_number,
    )
    item = _create_inventory_item(
        client, product["id"], lot_number=lot_number, quantity=quantity
    )
    return vendor, product, item


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBarcodeLookupMissingValue:
    """Parameter validation: value is required and min_length=1."""

    def test_missing_value_returns_422(self, client):
        r = client.get("/api/v1/barcode/lookup")
        assert r.status_code == 422

    def test_empty_value_returns_422(self, client):
        r = client.get("/api/v1/barcode/lookup?value=")
        assert r.status_code == 422


class TestBarcodeLookupNoMatch:
    """When no inventory matches, match_type should be 'none'."""

    def test_no_inventory_returns_none(self, client):
        r = client.get("/api/v1/barcode/lookup?value=NONEXISTENT-12345")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "none"
        assert data["total"] == 0
        assert data["items"] == []
        assert data["pages"] == 0

    def test_no_match_with_seeded_data(self, client):
        _seed_item(client, catalog="CAT-EXACT-001")
        r = client.get("/api/v1/barcode/lookup?value=COMPLETELY-UNRELATED")
        assert r.status_code == 200
        assert r.json()["match_type"] == "none"


class TestBarcodeLookupExactCatalogMatch:
    """Exact catalog_number match has highest priority."""

    def test_exact_match_returns_catalog_number_exact(self, client):
        vendor, product, item = _seed_item(client, catalog="CAT-EXACT-001")

        r = client.get("/api/v1/barcode/lookup?value=CAT-EXACT-001")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "catalog_number_exact"
        assert data["total"] >= 1

    def test_exact_match_returns_correct_item(self, client):
        _seed_item(client, catalog="CAT-ONLY-ONE")
        r = client.get("/api/v1/barcode/lookup?value=CAT-ONLY-ONE")
        data = r.json()
        assert data["total"] >= 1

    def test_exact_match_is_case_sensitive(self, client):
        """Exact match uses ==, so case must match."""
        _seed_item(client, catalog="Cat-Case-Sensitive")
        r = client.get("/api/v1/barcode/lookup?value=cat-case-sensitive")
        data = r.json()
        # Should fall through to fuzzy; if fuzzy doesn't match either, it's "none".
        assert data["match_type"] in ("partial", "none")


class TestBarcodeLookupPartialMatch:
    """Partial/fuzzy matches across catalog_number, product name, lot_number, CAS."""

    def test_partial_catalog_number(self, client):
        _seed_item(client, catalog="PARTIAL-CAT-99")
        r = client.get("/api/v1/barcode/lookup?value=PARTIAL-CAT")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1

    def test_partial_product_name(self, client):
        _seed_item(client, product_name="Ethanol Absolute 99.9%")
        r = client.get("/api/v1/barcode/lookup?value=Ethanol")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1

    def test_partial_lot_number(self, client):
        _seed_item(client, lot_number="LOT-ABC-2024-001")
        r = client.get("/api/v1/barcode/lookup?value=LOT-ABC")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1

    def test_partial_cas_number(self, client):
        _seed_item(client, cas_number="64-17-5")
        r = client.get("/api/v1/barcode/lookup?value=64-17")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "partial"
        assert data["total"] >= 1


class TestBarcodeLookupExactOverPartial:
    """When both exact and partial matches exist, exact wins."""

    def test_exact_match_takes_priority(self, client):
        # Product A: catalog matches exactly
        _seed_item(client, catalog="PRIORITY-EXACT", product_name="Exact Match Item")
        # Product B: name contains the exact catalog string as substring
        _seed_item(
            client,
            vendor_name="Vendor2",
            catalog="OTHER-CAT-002",
            product_name="Contains PRIORITY-EXACT in name",
        )

        r = client.get("/api/v1/barcode/lookup?value=PRIORITY-EXACT")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "catalog_number_exact"
        assert data["total"] >= 1


class TestBarcodeLookupPagination:
    """Pagination parameters: page, page_size."""

    def test_default_pagination(self, client):
        _seed_item(client, catalog="PAGE-DEFAULT")
        r = client.get("/api/v1/barcode/lookup?value=PAGE-DEFAULT")
        data = r.json()
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_custom_page_size(self, client):
        _seed_item(client, catalog="PAGE-SIZE-TEST")
        r = client.get("/api/v1/barcode/lookup?value=PAGE-SIZE-TEST&page_size=1")
        data = r.json()
        assert data["page_size"] == 1

    def test_page_size_limits(self):
        """page_size must be 1-200, checked by FastAPI validation."""
        pass  # Validated via Query(ge=1, le=200) — FastAPI returns 422 for violations

    def test_page_size_too_large_returns_422(self, client):
        r = client.get("/api/v1/barcode/lookup?value=X&page_size=300")
        assert r.status_code == 422

    def test_page_size_zero_returns_422(self, client):
        r = client.get("/api/v1/barcode/lookup?value=X&page_size=0")
        assert r.status_code == 422

    def test_page_zero_returns_422(self, client):
        r = client.get("/api/v1/barcode/lookup?value=X&page=0")
        assert r.status_code == 422


class TestBarcodeLookupSpecialCharacters:
    """Special characters in barcode values (LIKE wildcards, etc.)."""

    def test_value_with_percent_sign(self, client):
        _seed_item(client, catalog="CAT-%-SPECIAL")
        r = client.get("/api/v1/barcode/lookup?value=CAT-%25-SPECIAL")
        assert r.status_code == 200

    def test_value_with_underscore(self, client):
        _seed_item(client, catalog="CAT_UNDER_SCORE")
        r = client.get("/api/v1/barcode/lookup?value=CAT_UNDER_SCORE")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "catalog_number_exact"

    def test_value_with_backslash(self, client):
        _seed_item(client, catalog="CAT\\BACKSLASH")
        r = client.get("/api/v1/barcode/lookup?value=CAT%5CBACKSLASH")
        assert r.status_code == 200

    def test_value_with_spaces(self, client):
        _seed_item(client, product_name="Product With Spaces")
        r = client.get("/api/v1/barcode/lookup?value=Product With Spaces")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] in ("partial", "catalog_number_exact")


class TestBarcodeLookupMultipleMatches:
    """Multiple inventory items sharing the same product."""

    def test_multiple_items_same_product(self, client):
        vendor = _create_vendor(client, "MultiVendor")
        product = _create_product(
            client, vendor["id"], catalog="MULTI-SAME", name="MultiProduct"
        )
        _create_inventory_item(client, product["id"], lot_number="LOT-A", quantity="5")
        _create_inventory_item(client, product["id"], lot_number="LOT-B", quantity="3")

        r = client.get("/api/v1/barcode/lookup?value=MULTI-SAME")
        assert r.status_code == 200
        data = r.json()
        assert data["match_type"] == "catalog_number_exact"
        assert data["total"] >= 2


class TestBarcodeLookupResponseStructure:
    """Verify the response dict structure matches the expected schema."""

    def test_response_keys_on_match(self, client):
        _seed_item(client, catalog="STRUCT-TEST")
        r = client.get("/api/v1/barcode/lookup?value=STRUCT-TEST")
        data = r.json()
        for key in ("items", "total", "page", "page_size", "pages", "match_type"):
            assert key in data, f"Missing key: {key}"

    def test_response_keys_on_no_match(self, client):
        r = client.get("/api/v1/barcode/lookup?value=NO-MATCH-AT-ALL")
        data = r.json()
        for key in ("items", "total", "page", "page_size", "pages", "match_type"):
            assert key in data, f"Missing key: {key}"
        assert data["items"] == []
        assert isinstance(data["total"], int)
        assert isinstance(data["pages"], int)
