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
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor

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


# --- RAG SQL validation ---


def test_rag_unicode_bypass_blocked():
    """Unicode tricks should not bypass the SQL validator."""
    import pytest

    from lab_manager.services.rag import _validate_sql

    # Fullwidth semicolon (U+FF1B) normalizes to ASCII ';' under NFKC
    with pytest.raises(ValueError):
        _validate_sql("SELECT * FROM vendors\uff1bDROP TABLE vendors")

    # pg_catalog should be blocked
    with pytest.raises(ValueError):
        _validate_sql("SELECT * FROM pg_catalog.pg_shadow")


def test_rag_subquery_table_blocked():
    """Subqueries referencing disallowed tables should be blocked."""
    import pytest

    from lab_manager.services.rag import _validate_sql

    with pytest.raises(ValueError):
        _validate_sql("SELECT * FROM (SELECT * FROM pg_shadow) AS t")


# --- CAS number validation ---


def test_create_product_invalid_cas_rejected(client):
    """CAS numbers must match NNNNN-NN-N format or be null."""
    resp = client.post(
        "/api/products/",
        json={
            "catalog_number": "CAS-TEST",
            "name": "CAS Test",
            "cas_number": "not-a-cas-number",
        },
    )
    assert resp.status_code == 422


def test_create_product_valid_cas_accepted(client):
    resp = client.post(
        "/api/products/",
        json={
            "catalog_number": "CAS-OK",
            "name": "CAS Ok",
            "cas_number": "7732-18-5",
        },
    )
    assert resp.status_code == 201


def test_create_product_null_cas_accepted(client):
    resp = client.post(
        "/api/products/",
        json={
            "catalog_number": "CAS-NULL",
            "name": "No CAS",
        },
    )
    assert resp.status_code == 201


# --- Product update conflict ---


def test_update_product_catalog_conflict_returns_409(client, db_session):
    """PATCH catalog_number to collide with existing product should 409."""
    from lab_manager.models.product import Product
    from lab_manager.models.vendor import Vendor

    v = Vendor(name="Update Conflict Vendor")
    db_session.add(v)
    db_session.flush()
    p1 = Product(catalog_number="UPD-001", name="First", vendor_id=v.id)
    p2 = Product(catalog_number="UPD-002", name="Second", vendor_id=v.id)
    db_session.add_all([p1, p2])
    db_session.commit()

    resp = client.patch(
        f"/api/products/{p2.id}",
        json={"catalog_number": "UPD-001"},  # conflicts with p1
    )
    assert resp.status_code == 409


def test_update_product_invalid_cas_rejected(client, db_session):
    """PATCH with invalid CAS number should be rejected."""
    from lab_manager.models.product import Product

    p = Product(catalog_number="CAS-UPD", name="CAS Update Test")
    db_session.add(p)
    db_session.commit()

    resp = client.patch(
        f"/api/products/{p.id}",
        json={"cas_number": "invalid-cas"},
    )
    assert resp.status_code == 422
