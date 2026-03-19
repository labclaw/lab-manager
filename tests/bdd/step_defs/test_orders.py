"""Step definitions for order management BDD scenarios."""

import pytest
from pytest_bdd import given, when, then, scenario, parsers

FEATURE = "../features/orders.feature"


# --- Scenarios ---


@scenario(FEATURE, "Create a new purchase order")
def test_create_order():
    pass


@scenario(FEATURE, "Add items to an order")
def test_add_items():
    pass


@scenario(FEATURE, "Receive an order creates inventory")
def test_receive_order():
    pass


@scenario(FEATURE, "List orders filtered by vendor")
def test_list_orders_filtered():
    pass


@scenario(FEATURE, "Order detail includes items and vendor info")
def test_order_detail():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# --- Given steps ---


@given(
    parsers.parse('a vendor "{name}" exists'),
    target_fixture="vendor",
)
def create_vendor(api, name):
    r = api.post("/api/v1/vendors/", json={"name": name})
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('an order "{po}" exists'),
    target_fixture="order",
)
def create_order_given(api, vendor, po):
    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": po,
            "status": "pending",
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@given(
    parsers.parse('an order "{po}" with {n:d} items exists'),
    target_fixture="order",
)
def create_order_with_items(api, vendor, ctx, po, n):
    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": po,
            "status": "pending",
        },
    )
    assert r.status_code in (200, 201), r.text
    order = r.json()

    items = []
    for i in range(n):
        r = api.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": f"CAT-{i + 1:03d}",
                "description": f"Item {i + 1}",
                "quantity": i + 1,
                "unit": "EA",
            },
        )
        assert r.status_code in (200, 201), r.text
        items.append(r.json())

    ctx["order_items"] = items
    return order


@given("a product matching each order item exists", target_fixture="products")
def create_matching_products(api, vendor, ctx):
    products = []
    for oi in ctx["order_items"]:
        r = api.post(
            "/api/v1/products/",
            json={
                "name": oi["description"],
                "catalog_number": oi["catalog_number"],
                "vendor_id": vendor["id"],
            },
        )
        assert r.status_code in (200, 201), r.text
        product = r.json()

        # Link order item to product
        r2 = api.patch(
            f"/api/v1/orders/{oi['order_id']}/items/{oi['id']}",
            json={"product_id": product["id"]},
        )
        assert r2.status_code == 200, r2.text
        # Update the cached order_item with the product_id
        oi["product_id"] = product["id"]

        products.append(product)
    return products


@given(
    parsers.parse('{n:d} orders for vendor "{name}"'),
)
def create_n_orders_for_vendor(api, vendor, ctx, n, name):
    # Reuse the Background vendor if name matches, otherwise create new
    vendors = ctx.setdefault("vendors", {})
    if vendor["name"] not in vendors:
        vendors[vendor["name"]] = vendor
    if name not in vendors:
        r = api.post("/api/v1/vendors/", json={"name": name})
        assert r.status_code in (200, 201), r.text
        vendors[name] = r.json()
    v = vendors[name]

    for i in range(n):
        r = api.post(
            "/api/v1/orders/",
            json={
                "vendor_id": v["id"],
                "po_number": f"PO-{name[:3].upper()}-{i + 1:03d}",
                "status": "pending",
            },
        )
        assert r.status_code in (200, 201), r.text


@given(
    parsers.parse("an order with {n:d} items exists"),
    target_fixture="order",
)
def create_order_with_n_items(api, vendor, ctx, n):
    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": "PO-DETAIL-001",
            "status": "pending",
        },
    )
    assert r.status_code in (200, 201), r.text
    order = r.json()

    items = []
    for i in range(n):
        r = api.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "catalog_number": f"DET-{i + 1:03d}",
                "description": f"Detail item {i + 1}",
                "quantity": 1,
                "unit": "EA",
            },
        )
        assert r.status_code in (200, 201), r.text
        items.append(r.json())

    ctx["order_items"] = items
    return order


# --- When steps ---


@when(
    parsers.parse('I create an order with po_number "{po}" for the vendor'),
    target_fixture="order",
)
def create_order_when(api, vendor, po):
    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "po_number": po,
            "status": "pending",
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@when(
    parsers.parse(
        'I add an item with catalog "{catalog}" description "{desc}" '
        'quantity {qty:d} unit "{unit}"'
    ),
)
def add_item(api, order, ctx, catalog, desc, qty, unit):
    r = api.post(
        f"/api/v1/orders/{order['id']}/items",
        json={
            "catalog_number": catalog,
            "description": desc,
            "quantity": qty,
            "unit": unit,
        },
    )
    assert r.status_code in (200, 201), r.text
    items = ctx.setdefault("added_items", [])
    items.append(r.json())


@when(
    parsers.parse('I receive the order with received_by "{name}"'),
    target_fixture="receive_response",
)
def receive_order(api, db, order, ctx, name):
    from lab_manager.models.location import StorageLocation

    loc = StorageLocation(name="Receiving Bench")
    db.add(loc)
    db.flush()

    items_payload = [
        {
            "order_item_id": oi["id"],
            "quantity": oi["quantity"],
        }
        for oi in ctx["order_items"]
    ]

    r = api.post(
        f"/api/v1/orders/{order['id']}/receive",
        json={
            "items": items_payload,
            "location_id": loc.id,
            "received_by": name,
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@when(
    parsers.parse('I list orders for vendor "{name}"'),
    target_fixture="list_response",
)
def list_orders_for_vendor(api, ctx, name):
    v = ctx["vendors"][name]
    r = api.get(f"/api/v1/orders/?vendor_id={v['id']}")
    assert r.status_code == 200, r.text
    return r.json()


@when("I get the order detail", target_fixture="detail_response")
def get_order_detail(api, order, ctx):
    r = api.get(f"/api/v1/orders/{order['id']}")
    assert r.status_code == 200, r.text
    detail = r.json()

    # Also fetch items
    r_items = api.get(f"/api/v1/orders/{order['id']}/items")
    assert r_items.status_code == 200, r_items.text
    detail["_items"] = r_items.json()["items"]

    # Also fetch vendor info
    r_vendor = api.get(f"/api/v1/vendors/{detail['vendor_id']}")
    assert r_vendor.status_code == 200, r_vendor.text
    detail["_vendor"] = r_vendor.json()

    return detail


# --- Then steps ---


@then(parsers.parse('the order should be created with status "{status}"'))
def check_order_created_status(order, status):
    assert order["status"] == status


@then(parsers.parse('the order should have po_number "{po}"'))
def check_order_po(order, po):
    assert order["po_number"] == po


@then(parsers.parse("the order should have {n:d} items"))
def check_order_item_count(api, order, n):
    r = api.get(f"/api/v1/orders/{order['id']}/items")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == n


@then(parsers.parse('the first item should have catalog "{catalog}"'))
def check_first_item_catalog(api, order, catalog):
    r = api.get(f"/api/v1/orders/{order['id']}/items")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) > 0
    assert items[0]["catalog_number"] == catalog


@then(parsers.parse('the order status should be "{status}"'))
def check_order_status(api, order, status):
    r = api.get(f"/api/v1/orders/{order['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == status


@then(parsers.parse("{n:d} inventory items should be created"))
def check_inventory_count(receive_response, n):
    assert len(receive_response) == n


@then(parsers.parse('each inventory item should have status "{status}"'))
def check_inventory_status(receive_response, status):
    for item in receive_response:
        assert item["status"] == status


@then(parsers.parse("I should see {n:d} orders"))
def check_order_list_count(list_response, n):
    assert list_response["total"] == n


@then("the response should include vendor name")
def check_vendor_name(detail_response):
    assert detail_response["_vendor"]["name"]


@then(parsers.parse("the response should include {n:d} items with catalog numbers"))
def check_items_with_catalogs(detail_response, n):
    items = detail_response["_items"]
    assert len(items) == n
    for item in items:
        assert item["catalog_number"] is not None
