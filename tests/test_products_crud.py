"""Tests for products CRUD API endpoints."""

from fastapi.testclient import TestClient


def _create_vendor(client: TestClient, name: str = "Test Vendor") -> dict:
    r = client.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code == 201
    return r.json()


def _create_product(client: TestClient, **overrides) -> dict:
    body = {"name": "Test Product", "catalog_number": "CAT-001"}
    body.update(overrides)
    r = client.post("/api/v1/products/", json=body)
    assert r.status_code == 201
    return r.json()


class TestProductCreate:
    def test_create_product(self, client: TestClient):
        r = client.post(
            "/api/v1/products/",
            json={"name": "Ethanol", "catalog_number": "ETH-001"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Ethanol"
        assert data["catalog_number"] == "ETH-001"
        assert data["is_active"] is True

    def test_create_with_vendor(self, client: TestClient):
        vendor = _create_vendor(client)
        r = client.post(
            "/api/v1/products/",
            json={
                "name": "Buffer",
                "catalog_number": "BUF-001",
                "vendor_id": vendor["id"],
            },
        )
        assert r.status_code == 201
        assert r.json()["vendor_id"] == vendor["id"]

    def test_create_with_extra(self, client: TestClient):
        r = client.post(
            "/api/v1/products/",
            json={
                "name": "Extra Product",
                "catalog_number": "EXT-001",
                "extra": {"supplier": "Sigma", "lot_size": 100},
            },
        )
        assert r.status_code == 201
        assert r.json()["extra"]["supplier"] == "Sigma"

    def test_create_with_valid_cas(self, client: TestClient):
        r = client.post(
            "/api/v1/products/",
            json={
                "name": "CAS Product",
                "catalog_number": "CAS-001",
                "cas_number": "64-17-5",
            },
        )
        assert r.status_code == 201
        assert r.json()["cas_number"] == "64-17-5"

    def test_create_with_invalid_cas_returns_422(self, client: TestClient):
        r = client.post(
            "/api/v1/products/",
            json={
                "name": "Bad CAS",
                "catalog_number": "BCAS-001",
                "cas_number": "invalid",
            },
        )
        assert r.status_code == 422

    def test_create_empty_name_returns_422(self, client: TestClient):
        r = client.post(
            "/api/v1/products/",
            json={"name": "", "catalog_number": "EMPTY-001"},
        )
        assert r.status_code == 422

    def test_create_missing_catalog_number_returns_422(self, client: TestClient):
        r = client.post("/api/v1/products/", json={"name": "No Cat"})
        assert r.status_code == 422

    def test_create_long_catalog_number_returns_422(self, client: TestClient):
        r = client.post(
            "/api/v1/products/",
            json={"name": "Long Cat", "catalog_number": "x" * 101},
        )
        assert r.status_code == 422


class TestProductList:
    def test_list_products(self, client: TestClient):
        _create_product(client)
        r = client.get("/api/v1/products/")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_list_pagination(self, client: TestClient):
        for i in range(5):
            client.post(
                "/api/v1/products/",
                json={"name": f"Page-{i}", "catalog_number": f"PG-{i}"},
            )
        r = client.get("/api/v1/products/?page=1&page_size=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["pages"] >= 3

    def test_list_sort_by_name(self, client: TestClient):
        client.post(
            "/api/v1/products/", json={"name": "Zeta", "catalog_number": "Z-001"}
        )
        client.post(
            "/api/v1/products/", json={"name": "Alpha", "catalog_number": "A-001"}
        )
        r = client.get("/api/v1/products/?sort_by=name&sort_dir=asc")
        assert r.status_code == 200
        names = [i["name"] for i in r.json()["items"]]
        assert names == sorted(names)

    def test_list_filter_by_vendor(self, client: TestClient):
        vendor = _create_vendor(client)
        client.post(
            "/api/v1/products/",
            json={
                "name": "VProd",
                "catalog_number": "VP-001",
                "vendor_id": vendor["id"],
            },
        )
        r = client.get(f"/api/v1/products/?vendor_id={vendor['id']}")
        assert r.status_code == 200
        assert all(p["vendor_id"] == vendor["id"] for p in r.json()["items"])

    def test_list_filter_by_category(self, client: TestClient):
        client.post(
            "/api/v1/products/",
            json={
                "name": "CatProd",
                "catalog_number": "CP-001",
                "category": "reagents",
            },
        )
        r = client.get("/api/v1/products/?category=reagents")
        assert r.status_code == 200
        assert any(p.get("category") == "reagents" for p in r.json()["items"])


class TestProductGet:
    def test_get_product(self, client: TestClient):
        product = _create_product(client)
        r = client.get(f"/api/v1/products/{product['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == product["id"]

    def test_get_product_not_found(self, client: TestClient):
        r = client.get("/api/v1/products/99999")
        assert r.status_code == 404


class TestProductUpdate:
    def test_update_name(self, client: TestClient):
        product = _create_product(client)
        r = client.patch(f"/api/v1/products/{product['id']}", json={"name": "Updated"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"

    def test_update_vendor_id(self, client: TestClient):
        product = _create_product(client)
        vendor = _create_vendor(client)
        r = client.patch(
            f"/api/v1/products/{product['id']}", json={"vendor_id": vendor["id"]}
        )
        assert r.status_code == 200
        assert r.json()["vendor_id"] == vendor["id"]

    def test_remove_vendor_id(self, client: TestClient):
        vendor = _create_vendor(client)
        product = _create_product(client, vendor_id=vendor["id"])
        r = client.patch(f"/api/v1/products/{product['id']}", json={"vendor_id": None})
        assert r.status_code == 200
        assert r.json()["vendor_id"] is None

    def test_update_extra(self, client: TestClient):
        product = _create_product(client)
        r = client.patch(
            f"/api/v1/products/{product['id']}",
            json={"extra": {"supplier": "New", "notes": "Changed"}},
        )
        assert r.status_code == 200
        assert r.json()["extra"]["supplier"] == "New"

    def test_update_invalid_cas_returns_422(self, client: TestClient):
        product = _create_product(client)
        r = client.patch(
            f"/api/v1/products/{product['id']}", json={"cas_number": "bad"}
        )
        assert r.status_code == 422

    def test_update_clear_cas(self, client: TestClient):
        product = _create_product(client, cas_number="64-17-5")
        r = client.patch(f"/api/v1/products/{product['id']}", json={"cas_number": ""})
        assert r.status_code == 200
        assert r.json().get("cas_number") is None

    def test_update_no_body(self, client: TestClient):
        product = _create_product(client)
        r = client.patch(f"/api/v1/products/{product['id']}", json={})
        assert r.status_code == 200
        assert r.json()["name"] == product["name"]


class TestProductDelete:
    def test_delete_product(self, client: TestClient):
        product = _create_product(client)
        r = client.delete(f"/api/v1/products/{product['id']}")
        assert r.status_code == 204
        r2 = client.get(f"/api/v1/products/{product['id']}")
        assert r2.status_code == 404

    def test_delete_not_found(self, client: TestClient):
        r = client.delete("/api/v1/products/99999")
        assert r.status_code == 404


class TestProductSubResources:
    def test_inventory_empty(self, client: TestClient):
        product = _create_product(client)
        r = client.get(f"/api/v1/products/{product['id']}/inventory")
        assert r.status_code == 200
        assert isinstance(r.json()["items"], list)

    def test_inventory_not_found_product(self, client: TestClient):
        r = client.get("/api/v1/products/99999/inventory")
        assert r.status_code == 404

    def test_orders_empty(self, client: TestClient):
        product = _create_product(client)
        r = client.get(f"/api/v1/products/{product['id']}/orders")
        assert r.status_code == 200
        assert isinstance(r.json()["items"], list)

    def test_orders_not_found_product(self, client: TestClient):
        r = client.get("/api/v1/products/99999/orders")
        assert r.status_code == 404
