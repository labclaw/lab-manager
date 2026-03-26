"""Batch CSV import tests."""

from __future__ import annotations

import io


def _csv_upload(client, endpoint: str, csv_content: str):
    """Helper to upload CSV content to an import endpoint."""
    return client.post(
        endpoint,
        files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )


def test_import_products(client):
    # Create a vendor first
    client.post("/api/v1/vendors/", json={"name": "Sigma"})

    csv = "catalog_number,name,vendor_name,category,unit\nS1234,Acetone,Sigma,solvent,mL\nS5678,Ethanol,Sigma,solvent,mL"
    r = _csv_upload(client, "/api/v1/import/products", csv)
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 2
    assert data["errors"] == []


def test_import_products_skip_duplicate(client):
    client.post("/api/v1/vendors/", json={"name": "Fisher"})
    csv = "catalog_number,name,vendor_name\nA001,Product A,Fisher"
    _csv_upload(client, "/api/v1/import/products", csv)
    # Import again — should skip
    r = _csv_upload(client, "/api/v1/import/products", csv)
    assert r.json()["skipped"] == 1
    assert r.json()["created"] == 0


def test_import_products_missing_fields(client):
    csv = "catalog_number,name\n,Missing Name\nCAT1,"
    r = _csv_upload(client, "/api/v1/import/products", csv)
    assert r.json()["errors"][0]["row"] == 2
    assert r.json()["errors"][1]["row"] == 3


def test_import_inventory(client):
    # Setup: product
    client.post(
        "/api/v1/products/",
        json={"catalog_number": "V100", "name": "Beaker"},
    )

    csv = "product_catalog_number,quantity,lot_number,unit\nV100,10,LOT001,ea"
    r = _csv_upload(client, "/api/v1/import/inventory", csv)
    assert r.status_code == 200
    data = r.json()
    assert data["created"] == 1


def test_import_inventory_bad_quantity(client):
    client.post(
        "/api/v1/products/",
        json={"catalog_number": "X1", "name": "Thing"},
    )
    csv = "product_catalog_number,quantity\nX1,abc"
    r = _csv_upload(client, "/api/v1/import/inventory", csv)
    assert r.json()["errors"][0]["error"].startswith("Invalid quantity")


def test_import_inventory_product_not_found(client):
    csv = "product_catalog_number,quantity\nNONEXISTENT,5"
    r = _csv_upload(client, "/api/v1/import/inventory", csv)
    assert r.json()["errors"][0]["error"].startswith("Product not found")


def test_import_empty_csv(client):
    r = _csv_upload(client, "/api/v1/import/products", "")
    assert r.status_code == 422


def test_import_products_with_dates(client):
    csv = "catalog_number,name,shelf_life_days,is_hazardous\nH001,HCl,365,true"
    r = _csv_upload(client, "/api/v1/import/products", csv)
    assert r.json()["created"] == 1
