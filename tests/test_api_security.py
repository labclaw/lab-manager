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


# --- Document path traversal & status validation ---


def test_create_document_path_traversal_rejected(client):
    resp = client.post(
        "/api/documents/",
        json={
            "file_path": "../../../etc/passwd",
            "file_name": "traversal.pdf",
        },
    )
    assert resp.status_code == 422


def test_create_document_etc_path_rejected(client):
    resp = client.post(
        "/api/documents/",
        json={
            "file_path": "/etc/shadow",
            "file_name": "shadow.pdf",
        },
    )
    assert resp.status_code == 422


def test_create_document_status_invalid_rejected(client):
    resp = client.post(
        "/api/documents/",
        json={
            "file_path": "/uploads/test.pdf",
            "file_name": "test.pdf",
            "status": "hacked",
        },
    )
    assert resp.status_code == 422


def test_create_document_valid_status_accepted(client):
    resp = client.post(
        "/api/documents/",
        json={
            "file_path": "/uploads/ok.pdf",
            "file_name": "ok.pdf",
            "status": "pending",
        },
    )
    assert resp.status_code == 201
