"""Test full CRUD, pagination, filtering, sorting, and relationship endpoints."""


# =====================
#  Vendor endpoints
# =====================


def test_vendor_update(client):
    resp = client.post("/api/vendors/", json={"name": "OldName"})
    vid = resp.json()["id"]
    resp = client.patch(f"/api/vendors/{vid}", json={"name": "NewName"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "NewName"


def test_vendor_update_not_found(client):
    resp = client.patch("/api/vendors/999", json={"name": "X"})
    assert resp.status_code == 404


def test_vendor_delete(client):
    resp = client.post("/api/vendors/", json={"name": "ToDelete"})
    vid = resp.json()["id"]
    resp = client.delete(f"/api/vendors/{vid}")
    assert resp.status_code == 204
    resp = client.get(f"/api/vendors/{vid}")
    assert resp.status_code == 404


def test_vendor_delete_not_found(client):
    resp = client.delete("/api/vendors/999")
    assert resp.status_code == 404


def test_vendor_list_pagination(client):
    for i in range(5):
        client.post("/api/vendors/", json={"name": f"V{i}"})
    resp = client.get("/api/vendors/?page=1&page_size=2")
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["pages"] == 3


def test_vendor_list_filter_name(client):
    client.post("/api/vendors/", json={"name": "Thermo Fisher"})
    client.post("/api/vendors/", json={"name": "Sigma-Aldrich"})
    resp = client.get("/api/vendors/?name=Thermo")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Thermo Fisher"


def test_vendor_list_search(client):
    client.post("/api/vendors/", json={"name": "Bio-Rad", "email": "info@biorad.com"})
    client.post("/api/vendors/", json={"name": "Sigma"})
    resp = client.get("/api/vendors/?search=biorad")
    data = resp.json()
    assert data["total"] >= 1


def test_vendor_list_sorting(client):
    client.post("/api/vendors/", json={"name": "Zzz Vendor"})
    client.post("/api/vendors/", json={"name": "Aaa Vendor"})
    resp = client.get("/api/vendors/?sort_by=name&sort_dir=asc")
    items = resp.json()["items"]
    assert items[0]["name"] <= items[-1]["name"]

    resp = client.get("/api/vendors/?sort_by=name&sort_dir=desc")
    items = resp.json()["items"]
    assert items[0]["name"] >= items[-1]["name"]


def test_vendor_products_relationship(client):
    vr = client.post("/api/vendors/", json={"name": "VendorA"})
    vid = vr.json()["id"]
    client.post(
        "/api/products/",
        json={"catalog_number": "CAT1", "name": "Prod1", "vendor_id": vid},
    )
    resp = client.get(f"/api/vendors/{vid}/products")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["catalog_number"] == "CAT1"


def test_vendor_orders_relationship(client):
    vr = client.post("/api/vendors/", json={"name": "VendorB"})
    vid = vr.json()["id"]
    client.post("/api/orders/", json={"vendor_id": vid, "status": "pending"})
    resp = client.get(f"/api/vendors/{vid}/orders")
    data = resp.json()
    assert data["total"] == 1


def test_vendor_relationship_not_found(client):
    resp = client.get("/api/vendors/999/products")
    assert resp.status_code == 404


# =====================
#  Product endpoints
# =====================


def test_product_update(client):
    resp = client.post(
        "/api/products/", json={"catalog_number": "C1", "name": "OldProd"}
    )
    pid = resp.json()["id"]
    resp = client.patch(f"/api/products/{pid}", json={"name": "NewProd"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "NewProd"


def test_product_delete(client):
    resp = client.post(
        "/api/products/", json={"catalog_number": "C2", "name": "DelProd"}
    )
    pid = resp.json()["id"]
    resp = client.delete(f"/api/products/{pid}")
    assert resp.status_code == 204
    assert client.get(f"/api/products/{pid}").status_code == 404


def test_product_list_filters(client):
    vr = client.post("/api/vendors/", json={"name": "ProdVendor"})
    vid = vr.json()["id"]
    client.post(
        "/api/products/",
        json={
            "catalog_number": "AB100",
            "name": "Alpha Beta",
            "vendor_id": vid,
            "category": "antibodies",
        },
    )
    client.post(
        "/api/products/",
        json={"catalog_number": "CD200", "name": "Gamma", "category": "reagents"},
    )

    # filter by vendor_id
    resp = client.get(f"/api/products/?vendor_id={vid}")
    assert resp.json()["total"] == 1

    # filter by category
    resp = client.get("/api/products/?category=antibodies")
    assert resp.json()["total"] == 1

    # filter by catalog_number
    resp = client.get("/api/products/?catalog_number=AB")
    assert resp.json()["total"] >= 1

    # search
    resp = client.get("/api/products/?search=Alpha")
    assert resp.json()["total"] >= 1


def test_product_inventory_relationship(client):
    pr = client.post(
        "/api/products/", json={"catalog_number": "INV1", "name": "InvProd"}
    )
    pid = pr.json()["id"]
    client.post("/api/inventory/", json={"product_id": pid, "quantity_on_hand": 10})
    resp = client.get(f"/api/products/{pid}/inventory")
    assert resp.json()["total"] == 1


def test_product_orders_relationship(client):
    pr = client.post(
        "/api/products/", json={"catalog_number": "ORD1", "name": "OrdProd"}
    )
    pid = pr.json()["id"]
    # Create order and item
    orr = client.post("/api/orders/", json={"status": "pending"})
    oid = orr.json()["id"]
    client.post(
        f"/api/orders/{oid}/items",
        json={"order_id": oid, "product_id": pid, "catalog_number": "ORD1"},
    )
    resp = client.get(f"/api/products/{pid}/orders")
    assert resp.json()["total"] == 1


# =====================
#  Order endpoints
# =====================


def test_order_update(client):
    resp = client.post("/api/orders/", json={"status": "pending"})
    oid = resp.json()["id"]
    resp = client.patch(f"/api/orders/{oid}", json={"status": "shipped"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "shipped"


def test_order_soft_delete(client):
    resp = client.post("/api/orders/", json={"status": "pending"})
    oid = resp.json()["id"]
    resp = client.delete(f"/api/orders/{oid}")
    assert resp.status_code == 204
    # Should still exist but with status=deleted
    resp = client.get(f"/api/orders/{oid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


def test_order_list_filters(client):
    vr = client.post("/api/vendors/", json={"name": "OrderVendor"})
    vid = vr.json()["id"]
    client.post(
        "/api/orders/",
        json={
            "vendor_id": vid,
            "status": "received",
            "po_number": "PO-999",
            "order_date": "2026-01-15",
            "received_by": "John",
        },
    )
    client.post("/api/orders/", json={"status": "pending"})

    # filter by vendor_id
    resp = client.get(f"/api/orders/?vendor_id={vid}")
    assert resp.json()["total"] == 1

    # filter by status
    resp = client.get("/api/orders/?status=received")
    assert resp.json()["total"] >= 1

    # filter by po_number
    resp = client.get("/api/orders/?po_number=PO-999")
    assert resp.json()["total"] >= 1

    # filter by date range
    resp = client.get("/api/orders/?date_from=2026-01-01&date_to=2026-02-01")
    assert resp.json()["total"] >= 1

    # filter by received_by
    resp = client.get("/api/orders/?received_by=John")
    assert resp.json()["total"] >= 1


def test_order_list_pagination(client):
    resp = client.get("/api/orders/?page=1&page_size=10")
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data


# =====================
#  Order Items endpoints
# =====================


def test_order_items_crud(client):
    orr = client.post("/api/orders/", json={"status": "pending"})
    oid = orr.json()["id"]

    # Create item
    resp = client.post(
        f"/api/orders/{oid}/items",
        json={"order_id": oid, "catalog_number": "X100", "quantity": 5},
    )
    assert resp.status_code == 201
    iid = resp.json()["id"]

    # List items
    resp = client.get(f"/api/orders/{oid}/items")
    assert resp.json()["total"] == 1

    # Get item
    resp = client.get(f"/api/orders/{oid}/items/{iid}")
    assert resp.status_code == 200
    assert resp.json()["catalog_number"] == "X100"

    # Update item
    resp = client.patch(f"/api/orders/{oid}/items/{iid}", json={"lot_number": "LOT-1"})
    assert resp.status_code == 200
    assert resp.json()["lot_number"] == "LOT-1"

    # Delete item
    resp = client.delete(f"/api/orders/{oid}/items/{iid}")
    assert resp.status_code == 204
    resp = client.get(f"/api/orders/{oid}/items/{iid}")
    assert resp.status_code == 404


def test_order_items_filter(client):
    orr = client.post("/api/orders/", json={"status": "pending"})
    oid = orr.json()["id"]
    client.post(
        f"/api/orders/{oid}/items",
        json={
            "order_id": oid,
            "catalog_number": "AB100",
            "lot_number": "LOT-A",
        },
    )
    client.post(
        f"/api/orders/{oid}/items",
        json={"order_id": oid, "catalog_number": "CD200", "lot_number": "LOT-B"},
    )

    resp = client.get(f"/api/orders/{oid}/items?catalog_number=AB")
    assert resp.json()["total"] == 1

    resp = client.get(f"/api/orders/{oid}/items?lot_number=LOT-B")
    assert resp.json()["total"] == 1


# =====================
#  Inventory endpoints
# =====================


def test_inventory_update(client):
    resp = client.post(
        "/api/inventory/", json={"quantity_on_hand": 10, "status": "available"}
    )
    iid = resp.json()["id"]
    resp = client.patch(f"/api/inventory/{iid}", json={"quantity_on_hand": 5})
    assert resp.status_code == 200
    assert float(resp.json()["quantity_on_hand"]) == 5


def test_inventory_soft_delete(client):
    resp = client.post(
        "/api/inventory/", json={"quantity_on_hand": 3, "status": "available"}
    )
    iid = resp.json()["id"]
    resp = client.delete(f"/api/inventory/{iid}")
    assert resp.status_code == 204
    resp = client.get(f"/api/inventory/{iid}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


def test_inventory_list_filters(client):
    pr = client.post(
        "/api/products/", json={"catalog_number": "FP1", "name": "FilterProd"}
    )
    pid = pr.json()["id"]
    client.post(
        "/api/inventory/",
        json={
            "product_id": pid,
            "status": "available",
            "expiry_date": "2026-06-01",
            "quantity_on_hand": 10,
        },
    )
    client.post(
        "/api/inventory/",
        json={"status": "expired", "quantity_on_hand": 0},
    )

    # filter by product_id
    resp = client.get(f"/api/inventory/?product_id={pid}")
    assert resp.json()["total"] == 1

    # filter by status
    resp = client.get("/api/inventory/?status=available")
    assert resp.json()["total"] >= 1

    # filter by expiring_before
    resp = client.get("/api/inventory/?expiring_before=2026-12-31")
    assert resp.json()["total"] >= 1


def test_inventory_list_pagination(client):
    resp = client.get("/api/inventory/?page=1&page_size=10")
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data


# =====================
#  Document endpoints
# =====================


def test_document_update_full(client):
    resp = client.post(
        "/api/documents/",
        json={
            "file_path": "/tmp/test.pdf",
            "file_name": "test_upd.pdf",
            "status": "pending",
        },
    )
    did = resp.json()["id"]
    resp = client.patch(
        f"/api/documents/{did}",
        json={"vendor_name": "NewVendor", "document_type": "invoice"},
    )
    assert resp.status_code == 200
    assert resp.json()["vendor_name"] == "NewVendor"
    assert resp.json()["document_type"] == "invoice"


def test_document_soft_delete(client):
    resp = client.post(
        "/api/documents/",
        json={
            "file_path": "/tmp/del.pdf",
            "file_name": "del.pdf",
            "status": "pending",
        },
    )
    did = resp.json()["id"]
    resp = client.delete(f"/api/documents/{did}")
    assert resp.status_code == 204
    resp = client.get(f"/api/documents/{did}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"


def test_document_list_filters(client):
    client.post(
        "/api/documents/",
        json={
            "file_path": "/tmp/a.pdf",
            "file_name": "a_filter.pdf",
            "status": "pending",
            "document_type": "packing_list",
            "vendor_name": "Sigma",
        },
    )
    client.post(
        "/api/documents/",
        json={
            "file_path": "/tmp/b.pdf",
            "file_name": "b_filter.pdf",
            "status": "approved",
            "document_type": "invoice",
            "vendor_name": "Thermo",
        },
    )

    # filter by status
    resp = client.get("/api/documents/?status=pending")
    assert resp.json()["total"] >= 1

    # filter by document_type
    resp = client.get("/api/documents/?document_type=invoice")
    assert resp.json()["total"] >= 1

    # filter by vendor_name
    resp = client.get("/api/documents/?vendor_name=Sigma")
    assert resp.json()["total"] >= 1

    # search
    resp = client.get("/api/documents/?search=a_filter")
    assert resp.json()["total"] >= 1


def test_document_list_pagination(client):
    resp = client.get("/api/documents/?page=1&page_size=10")
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "pages" in data


def test_document_list_sorting(client):
    resp = client.get("/api/documents/?sort_by=id&sort_dir=desc")
    assert resp.status_code == 200
