"""Security and validation tests for API endpoints."""


def test_create_product_empty_catalog_number_rejected(client):
    resp = client.post(
        "/api/products/",
        json={
            "catalog_number": "",
            "name": "Test Product",
        },
    )
    assert resp.status_code == 422


def test_create_product_duplicate_returns_409(client, db_session):
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.product import Product

    v = Vendor(name="409 Vendor")
    db_session.add(v)
    db_session.flush()
    p = Product(catalog_number="DUP-001", name="Existing", vendor_id=v.id)
    db_session.add(p)
    db_session.commit()

    resp = client.post(
        "/api/products/",
        json={
            "catalog_number": "DUP-001",
            "name": "Duplicate",
            "vendor_id": v.id,
        },
    )
    assert resp.status_code == 409


def test_create_product_name_too_long_rejected(client):
    resp = client.post(
        "/api/products/",
        json={
            "catalog_number": "CAT-1",
            "name": "X" * 501,
        },
    )
    assert resp.status_code == 422
