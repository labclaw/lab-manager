"""Step definitions for order edge case BDD scenarios."""

import itertools

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/orders_edge_cases.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Get non-existent order returns 404")
def test_get_nonexistent_order():
    pass


@scenario(FEATURE, "Update order status")
def test_update_order_status():
    pass


@scenario(FEATURE, "Delete order soft-deletes")
def test_delete_order():
    pass


@scenario(FEATURE, "Get non-existent order item returns 404")
def test_get_nonexistent_order_item():
    pass


@scenario(FEATURE, "Delete an order item")
def test_delete_order_item():
    pass


@scenario(FEATURE, "List orders with pagination")
def test_list_orders_paginated():
    pass


@scenario(FEATURE, "List orders sorted by po_number descending")
def test_list_orders_sorted():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Given steps ---


@given(
    parsers.parse('an order test vendor "{name}" exists'),
    target_fixture="edge_vendor",
)
def create_edge_vendor(api, name):
    r = api.post("/api/vendors/", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


@given(
    parsers.parse('an order "{po}" exists for edge testing'),
    target_fixture="edge_order",
)
def create_edge_order(api, edge_vendor, po):
    r = api.post(
        "/api/orders/",
        json={
            "vendor_id": edge_vendor["id"],
            "po_number": po,
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@given(
    parsers.parse('an order "{po}" with {n:d} item exists for edge testing'),
    target_fixture="edge_order",
)
def create_edge_order_with_items(api, edge_vendor, ctx, po, n):
    r = api.post(
        "/api/orders/",
        json={
            "vendor_id": edge_vendor["id"],
            "po_number": po,
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    order = r.json()

    items = []
    for i in range(n):
        r = api.post(
            f"/api/orders/{order['id']}/items",
            json={
                "catalog_number": f"EDGE-{next(_seq):05d}",
                "description": f"Edge Item {i + 1}",
                "quantity": 1,
                "unit": "EA",
            },
        )
        assert r.status_code == 201, r.text
        items.append(r.json())

    ctx["edge_order_items"] = items
    return order


@given(parsers.parse("{n:d} orders exist for edge testing"))
def create_n_edge_orders(api, edge_vendor, n):
    for i in range(n):
        r = api.post(
            "/api/orders/",
            json={
                "vendor_id": edge_vendor["id"],
                "po_number": f"PO-PAGN-{next(_seq):05d}",
                "status": "pending",
            },
        )
        assert r.status_code == 201, r.text


@given(parsers.parse("{n:d} orders with sequential POs exist for edge testing"))
def create_sequential_orders(api, edge_vendor, ctx, n):
    pos = []
    for i in range(n):
        po = f"PO-SORT-{chr(65 + i)}"
        r = api.post(
            "/api/orders/",
            json={
                "vendor_id": edge_vendor["id"],
                "po_number": po,
                "status": "pending",
            },
        )
        assert r.status_code == 201, r.text
        pos.append(po)
    ctx["sequential_pos"] = pos


# --- When steps ---


@when(parsers.parse("I get order with id {oid:d}"), target_fixture="order_resp")
def get_order_nonexistent(api, oid):
    return api.get(f"/api/orders/{oid}")


@when(
    parsers.parse('I update the order status to "{status}"'),
    target_fixture="order_resp",
)
def update_order_status(api, edge_order, status):
    r = api.patch(f"/api/orders/{edge_order['id']}", json={"status": status})
    assert r.status_code == 200, r.text
    return r


@when("I delete the order", target_fixture="order_resp")
def delete_order(api, edge_order):
    return api.delete(f"/api/orders/{edge_order['id']}")


@when(
    parsers.parse("I get order item {iid:d} from the order"),
    target_fixture="order_resp",
)
def get_order_item_nonexistent(api, edge_order, iid):
    return api.get(f"/api/orders/{edge_order['id']}/items/{iid}")


@when("I delete the first order item", target_fixture="order_resp")
def delete_first_order_item(api, edge_order, ctx):
    item = ctx["edge_order_items"][0]
    return api.delete(f"/api/orders/{edge_order['id']}/items/{item['id']}")


@when(
    parsers.parse("I list orders with page {page:d} and page_size {ps:d}"),
    target_fixture="order_list",
)
def list_orders_paginated(api, page, ps):
    r = api.get("/api/orders/", params={"page": page, "page_size": ps})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I list orders sorted by {field} {direction}"),
    target_fixture="order_list",
)
def list_orders_sorted(api, field, direction):
    r = api.get("/api/orders/", params={"sort_by": field, "sort_dir": direction})
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse("the order response status should be {code:d}"))
def check_order_response_status(order_resp, code):
    assert order_resp.status_code == code


@then(parsers.parse('the order should have status "{status}"'))
def check_order_status(order_resp, status):
    assert order_resp.json()["status"] == status


@then(parsers.parse("the order delete response should be {code:d}"))
def check_delete_status(order_resp, code):
    assert order_resp.status_code == code


@then(parsers.parse("the order item delete response should be {code:d}"))
def check_item_delete_status(order_resp, code):
    assert order_resp.status_code == code


@then(parsers.parse("the order should have {n:d} items"))
def check_order_items_count(api, edge_order, n):
    r = api.get(f"/api/orders/{edge_order['id']}/items")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == n


@then(parsers.parse("I should see {n:d} orders in the page"))
def check_page_count(order_list, n):
    assert len(order_list["items"]) == n


@then(parsers.parse("the total should be {n:d}"))
def check_total(order_list, n):
    assert order_list["total"] == n


@then("the first order PO should come last alphabetically")
def check_sorted_order(order_list, ctx):
    items = order_list["items"]
    pos = [o["po_number"] for o in items if o["po_number"].startswith("PO-SORT-")]
    # desc means C, B, A
    assert pos == sorted(pos, reverse=True), f"Expected descending, got {pos}"
