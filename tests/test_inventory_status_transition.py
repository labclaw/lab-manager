"""Tests for inventory PATCH status transition validation."""

from unittest.mock import patch


def _make_product(client, catalog="ST", name="StatusProd"):
    with patch("lab_manager.api.routes.products.index_product_record"):
        resp = client.post(
            "/api/v1/products/",
            json={"catalog_number": catalog, "name": name},
        )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def _make_inventory(client, product_id, status="available", qty=10):
    with patch("lab_manager.api.routes.inventory.index_inventory_record"):
        resp = client.post(
            "/api/v1/inventory/",
            json={
                "product_id": product_id,
                "quantity_on_hand": qty,
                "status": status,
            },
        )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def _patch_item(client, item_id, **kwargs):
    with patch("lab_manager.api.routes.inventory.index_inventory_record"):
        return client.patch(f"/api/v1/inventory/{item_id}", json=kwargs)


def test_patch_rejects_expired_to_available(client):
    """Cannot resurrect expired item via PATCH."""
    pid = _make_product(client, "ST1", "Prod1")
    iid = _make_inventory(client, pid, status="expired")

    resp = _patch_item(client, iid, status="available")
    assert resp.status_code == 422
    assert "Cannot transition" in resp.json()["detail"]


def test_patch_rejects_available_to_opened(client):
    """Cannot set opened via PATCH — must use /open endpoint."""
    pid = _make_product(client, "ST2", "Prod2")
    iid = _make_inventory(client, pid, status="available")

    resp = _patch_item(client, iid, status="opened")
    assert resp.status_code == 422
    assert "Cannot transition" in resp.json()["detail"]


def test_patch_rejects_available_to_disposed(client):
    """Cannot dispose via PATCH — must use /dispose endpoint."""
    pid = _make_product(client, "ST3", "Prod3")
    iid = _make_inventory(client, pid, status="available")

    resp = _patch_item(client, iid, status="disposed")
    assert resp.status_code == 422


def test_patch_allows_available_to_expired(client):
    """available -> expired is valid (no side-effects needed)."""
    pid = _make_product(client, "ST4", "Prod4")
    iid = _make_inventory(client, pid, status="available")

    resp = _patch_item(client, iid, status="expired")
    assert resp.status_code == 200
    assert resp.json()["status"] == "expired"


def test_patch_allows_same_status(client):
    """Setting the same status is allowed (idempotent)."""
    pid = _make_product(client, "ST5", "Prod5")
    iid = _make_inventory(client, pid, status="available")

    resp = _patch_item(client, iid, status="available")
    assert resp.status_code == 200
    assert resp.json()["status"] == "available"


def test_patch_allows_expired_to_disposed(client):
    """expired -> disposed is valid (no side-effects needed)."""
    pid = _make_product(client, "ST6", "Prod6")
    iid = _make_inventory(client, pid, status="expired")

    resp = _patch_item(client, iid, status="disposed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disposed"


def test_patch_no_status_change_still_works(client):
    """PATCH without status field should work as before."""
    pid = _make_product(client, "ST7", "Prod7")
    iid = _make_inventory(client, pid, status="available")

    resp = _patch_item(client, iid, notes="updated")
    assert resp.status_code == 200
    assert resp.json()["notes"] == "updated"
