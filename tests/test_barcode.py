"""Barcode and QR code generation tests."""

from __future__ import annotations


def _create_product_and_inventory(client):
    """Helper to create a product + inventory item."""
    p = client.post(
        "/api/v1/products/",
        json={"catalog_number": "BC-001", "name": "Test Chemical"},
    )
    product_id = p.json()["id"]
    inv = client.post(
        "/api/v1/inventory/",
        json={"product_id": product_id, "quantity_on_hand": 5, "lot_number": "L123"},
    )
    return inv.json()["id"], product_id


def test_inventory_qr(client):
    inv_id, _ = _create_product_and_inventory(client)
    r = client.get(f"/api/v1/barcode/inventory/{inv_id}/qr")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 100  # PNG has content


def test_inventory_barcode(client):
    inv_id, _ = _create_product_and_inventory(client)
    r = client.get(f"/api/v1/barcode/inventory/{inv_id}/barcode")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_inventory_qr_404(client):
    r = client.get("/api/v1/barcode/inventory/99999/qr")
    assert r.status_code == 404


def test_location_qr(client):
    loc = client.post("/api/v1/locations/", json={"name": "Lab 1"})
    loc_id = loc.json()["id"]
    r = client.get(f"/api/v1/barcode/location/{loc_id}/qr")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_location_barcode(client):
    loc = client.post("/api/v1/locations/", json={"name": "Freezer"})
    loc_id = loc.json()["id"]
    r = client.get(f"/api/v1/barcode/location/{loc_id}/barcode")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_product_qr(client):
    _, prod_id = _create_product_and_inventory(client)
    r = client.get(f"/api/v1/barcode/product/{prod_id}/qr")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_bulk_qr(client):
    inv_id, _ = _create_product_and_inventory(client)
    loc = client.post("/api/v1/locations/", json={"name": "Room X"})
    loc_id = loc.json()["id"]

    r = client.post(
        "/api/v1/barcode/bulk-qr",
        json={"inventory_ids": [inv_id], "location_ids": [loc_id]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["qr_base64"]  # Not empty


def test_qr_custom_size(client):
    inv_id, _ = _create_product_and_inventory(client)
    r = client.get(f"/api/v1/barcode/inventory/{inv_id}/qr?size=20")
    assert r.status_code == 200
    # Larger size = larger image
    large = len(r.content)

    r2 = client.get(f"/api/v1/barcode/inventory/{inv_id}/qr?size=5")
    small = len(r2.content)
    assert large > small
