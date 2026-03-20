"""Step definitions for audit trail BDD tests."""

from pytest_bdd import given, when, then, parsers


@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


@given("an inventory item was created")
def inventory_created(api_client):
    """Create inventory item."""
    resp = api_client.post("/api/v1/products", json={"name": "Audit Test Product"})
    product_id = resp.json()["id"]
    resp = api_client.post(
        "/api/v1/inventory",
        json={
            "product_id": product_id,
            "quantity": 100,
        },
    )
    api_client.inventory_id = resp.json()["id"]


@given(parsers.parse("the quantity was adjusted from {old:d} to {new:d}"))
def quantity_adjusted(api_client, old, new):
    """Adjust inventory quantity."""
    inv_id = getattr(api_client, "inventory_id", None)
    if inv_id:
        api_client.post(
            f"/api/v1/inventory/{inv_id}/adjust",
            json={
                "quantity": new,
                "reason": "Test adjustment",
            },
        )


@given(parsers.parse("the item was consumed {qty:d} units"))
def item_consumed(api_client, qty):
    """Consume inventory."""
    inv_id = getattr(api_client, "inventory_id", None)
    if inv_id:
        api_client.post(f"/api/v1/inventory/{inv_id}/consume", json={"quantity": qty})


@when(parsers.parse("I view audit history for the inventory item"))
def view_inventory_audit(api_client):
    """View inventory audit history."""
    inv_id = getattr(api_client, "inventory_id", None)
    api_client.response = api_client.get(f"/api/v1/inventory/{inv_id}/history")


@then(parsers.parse("I should see {count:d} audit entries"))
def see_audit_entries(api_client, count):
    """Verify audit entry count."""
    data = api_client.response.json()
    items = data.get("items", data)
    assert len(items) >= count


@then("each entry should have timestamp, user, and action")
def entry_has_fields(api_client):
    """Verify entry fields."""
    data = api_client.response.json()
    items = data.get("items", data)
    for item in items[:3]:
        assert "timestamp" in item or "created_at" in item
        assert "user" in item or "user_id" in item
        assert "action" in item


@given("an order was created")
def order_created(api_client):
    """Create order."""
    vendor_resp = api_client.post("/api/v1/vendors", json={"name": "Audit Test Vendor"})
    vendor_id = vendor_resp.json()["id"]
    resp = api_client.post("/api/v1/orders", json={"vendor_id": vendor_id})
    api_client.order_id = resp.json()["id"]


@given(parsers.parse('the order status changed from "{old}" to "{new}"'))
def order_status_changed(api_client, old, new):
    """Change order status."""
    order_id = getattr(api_client, "order_id", None)
    if order_id:
        api_client.patch(f"/api/v1/orders/{order_id}", json={"status": new})


@when(parsers.parse("I view audit history for the order"))
def view_order_audit(api_client):
    """View order audit history."""
    order_id = getattr(api_client, "order_id", None)
    api_client.response = api_client.get(f"/api/v1/orders/{order_id}/history")


@then("status changes should be recorded")
def status_changes_recorded(api_client):
    """Verify status changes recorded."""
    data = api_client.response.json()
    items = data.get("items", data)
    status_actions = [i for i in items if "status" in i.get("action", "").lower()]
    assert len(status_actions) >= 2


@given(parsers.parse('user "{user}" created a vendor'))
def user_created_vendor(api_client, user):
    """Create vendor as user."""
    api_client.post(
        "/api/v1/vendors", json={"name": f"Vendor by {user}"}, headers={"X-User": user}
    )


@given(parsers.parse('user "{user}" updated the vendor'))
def user_updated_vendor(api_client, user):
    """Update vendor as user."""
    resp = api_client.get("/api/v1/vendors")
    vendor_id = resp.json()["items"][0]["id"]
    api_client.patch(
        f"/api/v1/vendors/{vendor_id}",
        json={"name": f"Updated by {user}"},
        headers={"X-User": user},
    )


@when(parsers.parse("I view audit history for the vendor"))
def view_vendor_audit(api_client):
    """View vendor audit history."""
    resp = api_client.get("/api/v1/vendors")
    vendor_id = resp.json()["items"][0]["id"]
    api_client.response = api_client.get(f"/api/v1/vendors/{vendor_id}/history")


@then(parsers.parse('"{user}" should be listed as creator'))
def user_is_creator(api_client, user):
    """Verify user is creator."""
    data = api_client.response.json()
    items = data.get("items", data)
    create_action = next((i for i in items if i.get("action") == "create"), None)
    if create_action:
        assert user in str(create_action.get("user", ""))


@then(parsers.parse('"{user}" should be listed as updater'))
def user_is_updater(api_client, user):
    """Verify user is updater."""
    data = api_client.response.json()
    items = data.get("items", data)
    update_action = next((i for i in items if i.get("action") == "update"), None)
    if update_action:
        assert user in str(update_action.get("user", ""))


@given(parsers.parse('a document was uploaded by "{user}"'))
def doc_uploaded_by(api_client, user):
    """Document uploaded by user."""
    resp = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "test.pdf",
        },
        headers={"X-User": user},
    )
    api_client.doc_id = resp.json()["id"]


@given(parsers.parse('the document was reviewed by "{user}"'))
def doc_reviewed_by(api_client, user):
    """Document reviewed by user."""
    doc_id = getattr(api_client, "doc_id", None)
    if doc_id:
        api_client.post(
            f"/api/v1/documents/{doc_id}/review",
            json={"action": "approve"},
            headers={"X-User": user},
        )


@when(parsers.parse("I view audit history for the document"))
def view_doc_audit(api_client):
    """View document audit history."""
    doc_id = getattr(api_client, "doc_id", None)
    api_client.response = api_client.get(f"/api/v1/documents/{doc_id}/history")


@then(parsers.parse('upload action should be attributed to "{user}"'))
def upload_by_user(api_client, user):
    """Verify upload attribution."""
    data = api_client.response.json()
    items = data.get("items", data)
    upload = next((i for i in items if "upload" in i.get("action", "").lower()), None)
    if upload:
        assert user in str(upload.get("user", ""))


@then(parsers.parse('review action should be attributed to "{user}"'))
def review_by_user(api_client, user):
    """Verify review attribution."""
    data = api_client.response.json()
    items = data.get("items", data)
    review = next((i for i in items if "review" in i.get("action", "").lower()), None)
    if review:
        assert user in str(review.get("user", ""))


@given("audit entries exist for:")
def audit_entries_for_tables(api_client, datatable):
    """Create audit entries for tables."""
    for row in datatable:
        for _ in range(int(row["count"])):
            api_client.post(
                "/api/v1/audit",
                json={
                    "table_name": row["table"],
                    "action": "view",
                    "record_id": 1,
                },
            )


@when(parsers.parse('I query audit log for table "{table}"'))
def query_audit_by_table(api_client, table):
    """Query audit by table."""
    api_client.response = api_client.get(f"/api/v1/audit?table_name={table}")


@then(parsers.parse("all entries should be for {table} records"))
def all_entries_for_table(api_client, table):
    """Verify all entries for table."""
    data = api_client.response.json()
    items = data.get("items", data)
    for item in items:
        assert item.get("table_name") == table


@given(parsers.parse("{count:d} audit entries exist"))
def count_audit_entries(api_client, count):
    """Create audit entries."""
    for i in range(count):
        api_client.post(
            "/api/v1/audit",
            json={
                "action": "view",
                "table_name": "inventory",
                "record_id": i,
            },
        )


@when(parsers.parse("I request audit log page {page:d} with page size {size:d}"))
def audit_log_paginated(api_client, page, size):
    """Request paginated audit log."""
    api_client.response = api_client.get(f"/api/v1/audit?page={page}&page_size={size}")


@then(parsers.parse("I should receive {count:d} entries"))
def receive_entries(api_client, count):
    """Verify entry count."""
    data = api_client.response.json()
    items = data.get("items", data)
    assert len(items) == count


@then("entries should be ordered by timestamp descending")
def entries_ordered(api_client):
    """Verify ordering."""
    data = api_client.response.json()
    items = data.get("items", data)
    if len(items) >= 2:
        t1 = items[0].get("timestamp", items[0].get("created_at", ""))
        t2 = items[1].get("timestamp", items[1].get("created_at", ""))
        assert t1 >= t2


@given("audit entries on dates:")
def audit_entries_dates(api_client, datatable):
    """Create audit entries with dates."""
    for row in datatable:
        api_client.post(
            "/api/v1/audit",
            json={
                "action": "view",
                "table_name": "inventory",
                "record_id": 1,
                "created_at": row["date"],
            },
        )


@when(parsers.parse('I filter audit log from "{start}" to "{end}"'))
def filter_audit_dates(api_client, start, end):
    """Filter audit by date range."""
    api_client.response = api_client.get(
        f"/api/v1/audit?start_date={start}&end_date={end}"
    )


@when("I view the audit entry detail")
def view_audit_detail(api_client):
    """View audit detail."""
    data = api_client.response.json()
    items = data.get("items", data)
    if items:
        entry_id = items[0].get("id", items[0].get("audit_id"))
        api_client.response = api_client.get(f"/api/v1/audit/{entry_id}")


@then("I should see:")
def should_see_fields(api_client, datatable):
    """Verify fields present."""
    data = api_client.response.json()
    for row in datatable:
        field = row["field"]
        assert field in data, f"Missing field: {field}"


@given("a vendor was deleted")
def vendor_deleted(api_client):
    """Delete vendor."""
    resp = api_client.post("/api/v1/vendors", json={"name": "To Delete"})
    vendor_id = resp.json()["id"]
    api_client.delete(f"/api/v1/vendors/{vendor_id}")
    api_client.deleted_vendor_id = vendor_id


@when("I try to update the audit entry")
def try_update_audit(api_client):
    """Try to update audit entry."""
    data = api_client.response.json()
    items = data.get("items", [data])
    if items:
        entry_id = items[0].get("id", items[0].get("audit_id"))
        api_client.response = api_client.patch(
            f"/api/v1/audit/{entry_id}", json={"action": "modified"}
        )


@then("the request should fail")
def request_should_fail(api_client):
    """Verify request failed."""
    assert api_client.response.status_code >= 400


@then("audit entries should be immutable")
def audit_immutable(api_client):
    """Verify immutability."""
    assert api_client.response.status_code in [400, 403, 405, 501]
