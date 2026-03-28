"""Tests for vendor URL registry and reorder URL generation."""

from urllib.parse import parse_qs, urlparse

import pytest

from lab_manager.services.vendor_urls import VENDOR_SEARCH_URLS, get_reorder_url


def _assert_https_host(url: str, expected_host: str):
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == expected_host
    return parsed


def _assert_query_param(url: str, expected_host: str, key: str, expected_value: str):
    parsed = _assert_https_host(url, expected_host)
    assert parse_qs(parsed.query).get(key) == [expected_value]
    return parsed


@pytest.fixture
def client_without_search(client, monkeypatch):
    monkeypatch.setattr(
        "lab_manager.api.routes.vendors.index_vendor_record", lambda _: None
    )
    monkeypatch.setattr(
        "lab_manager.api.routes.products.index_product_record", lambda _: None
    )
    monkeypatch.setattr(
        "lab_manager.api.routes.inventory.index_inventory_record", lambda _: None
    )
    return client


class TestVendorSearchUrls:
    """Verify the VENDOR_SEARCH_URLS registry is well-formed."""

    def test_registry_not_empty(self):
        assert len(VENDOR_SEARCH_URLS) >= 20

    @pytest.mark.parametrize("vendor_key,url_pattern", VENDOR_SEARCH_URLS.items())
    def test_all_patterns_contain_catalog_placeholder(self, vendor_key, url_pattern):
        assert "{catalog}" in url_pattern, f"{vendor_key} pattern missing {{catalog}}"

    @pytest.mark.parametrize("vendor_key,url_pattern", VENDOR_SEARCH_URLS.items())
    def test_all_patterns_are_https(self, vendor_key, url_pattern):
        assert url_pattern.startswith("https://"), f"{vendor_key} not HTTPS"

    @pytest.mark.parametrize("vendor_key", VENDOR_SEARCH_URLS.keys())
    def test_all_keys_are_lowercase(self, vendor_key):
        assert vendor_key == vendor_key.lower()


class TestGetReorderUrl:
    """Test get_reorder_url with various vendor/catalog combinations."""

    def test_exact_match_sigma(self):
        url = get_reorder_url("Sigma-Aldrich", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_exact_match_thermo(self):
        url = get_reorder_url("Thermo Fisher", "A12345")
        assert url == "https://www.thermofisher.com/search/results?query=A12345"

    def test_substring_match_vendor_in_key(self):
        url = get_reorder_url("Bio-Rad Laboratories", "1234567")
        assert url is not None
        parsed = _assert_query_param(url, "www.bio-rad.com", "query", "1234567")
        assert parsed.path == "/en-us/search"

    def test_substring_match_key_in_vendor(self):
        url = get_reorder_url("VWR", "ABC-123")
        assert url is not None
        parsed = _assert_query_param(url, "us.vwr.com", "query", "ABC-123")
        assert parsed.path == "/store/search"

    def test_case_insensitive(self):
        url = get_reorder_url("ADDGENE", "12345")
        assert url is not None
        parsed = _assert_query_param(url, "www.addgene.org", "q", "12345")
        assert parsed.path == "/search/all/"

    def test_invitrogen_maps_to_thermofisher(self):
        url = get_reorder_url("Invitrogen", "INV-001")
        assert url is not None
        _assert_query_param(url, "www.thermofisher.com", "query", "INV-001")

    def test_milliporesigma_maps_to_sigmaaldrich(self):
        url = get_reorder_url("MilliporeSigma", "M5678")
        assert url is not None
        parsed = _assert_https_host(url, "www.sigmaaldrich.com")
        assert parsed.path.split("/")[-1] == "M5678"

    def test_unknown_vendor_falls_back_to_google(self):
        url = get_reorder_url("Unknown Vendor Inc", "XYZ-999")
        assert url is not None
        parsed = _assert_query_param(
            url,
            "www.google.com",
            "q",
            "Unknown Vendor Inc XYZ-999 order",
        )
        assert parsed.path == "/search"

    def test_empty_vendor_returns_none(self):
        assert get_reorder_url("", "S1234") is None

    def test_empty_catalog_returns_none(self):
        assert get_reorder_url("Sigma-Aldrich", "") is None

    def test_both_empty_returns_none(self):
        assert get_reorder_url("", "") is None

    def test_whitespace_vendor_stripped(self):
        url = get_reorder_url("  Sigma-Aldrich  ", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_mcmaster_carr(self):
        url = get_reorder_url("McMaster-Carr", "91251A")
        assert url is not None
        parsed = _assert_https_host(url, "www.mcmaster.com")
        assert parsed.path.strip("/") == "91251A"


class TestGetReorderUrlEndpoint:
    """Test the API endpoint for reorder URL generation."""

    def test_reorder_url_with_known_vendor(self, client_without_search):
        # Create vendor
        vr = client_without_search.post(
            "/api/v1/vendors/", json={"name": "Sigma-Aldrich"}
        )
        vendor_id = vr.json()["id"]

        # Create product
        pr = client_without_search.post(
            "/api/v1/products/",
            json={
                "name": "Test Chemical",
                "catalog_number": "S1234",
                "vendor_id": vendor_id,
            },
        )
        product_id = pr.json()["id"]

        # Create inventory item
        ir = client_without_search.post(
            "/api/v1/inventory/",
            json={"product_id": product_id, "quantity_on_hand": 5},
        )
        item_id = ir.json()["id"]

        # Get reorder URL
        resp = client_without_search.get(f"/api/v1/inventory/{item_id}/reorder-url")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vendor"] == "Sigma-Aldrich"
        assert data["catalog_number"] == "S1234"
        parsed = _assert_https_host(data["url"], "www.sigmaaldrich.com")
        assert parsed.path.split("/")[-1] == "S1234"

    def test_reorder_url_unknown_vendor_google_fallback(self, client_without_search):
        vr = client_without_search.post(
            "/api/v1/vendors/", json={"name": "Unknown Lab Supply"}
        )
        vendor_id = vr.json()["id"]

        pr = client_without_search.post(
            "/api/v1/products/",
            json={
                "name": "Mystery Reagent",
                "catalog_number": "UNK-001",
                "vendor_id": vendor_id,
            },
        )
        product_id = pr.json()["id"]

        ir = client_without_search.post(
            "/api/v1/inventory/",
            json={"product_id": product_id, "quantity_on_hand": 1},
        )
        item_id = ir.json()["id"]

        resp = client_without_search.get(f"/api/v1/inventory/{item_id}/reorder-url")
        assert resp.status_code == 200
        data = resp.json()
        parsed = _assert_query_param(
            data["url"],
            "www.google.com",
            "q",
            "Unknown Lab Supply UNK-001 order",
        )
        assert parsed.path == "/search"

    def test_reorder_url_no_vendor_returns_none(self, client_without_search):
        # Product with no vendor
        pr = client_without_search.post(
            "/api/v1/products/",
            json={"name": "Orphan Product", "catalog_number": "ORP-001"},
        )
        product_id = pr.json()["id"]

        ir = client_without_search.post(
            "/api/v1/inventory/",
            json={"product_id": product_id, "quantity_on_hand": 1},
        )
        item_id = ir.json()["id"]

        resp = client_without_search.get(f"/api/v1/inventory/{item_id}/reorder-url")
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] is None
        assert data["vendor"] is None

    def test_reorder_url_not_found(self, client):
        resp = client.get("/api/v1/inventory/99999/reorder-url")
        assert resp.status_code == 404
