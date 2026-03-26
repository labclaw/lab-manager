"""Step definitions for inventory edge case BDD scenarios."""

import itertools
from datetime import date, timedelta

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/inventory_edge_cases.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Get non-existent inventory item returns 404")
def test_get_nonexistent():
    pass


@scenario(FEATURE, "Consume from non-existent item returns 404")
def test_consume_nonexistent():
    pass


@scenario(FEATURE, "Cannot consume zero quantity")
def test_consume_zero():
    pass


@scenario(FEATURE, "Cannot adjust to negative quantity")
def test_adjust_negative():
    pass


@scenario(FEATURE, "Cannot open an already-opened item")
def test_open_already_opened():
    pass


@scenario(FEATURE, "Cannot consume from disposed item")
def test_consume_disposed():
    pass


@scenario(FEATURE, "List inventory items")
def test_list_inventory():
    pass


@scenario(FEATURE, "Filter inventory by status")
def test_filter_by_status():
    pass


@scenario(FEATURE, "Low stock report")
def test_low_stock():
    pass


@scenario(FEATURE, "Expiring items report")
def test_expiring():
    pass


@scenario(FEATURE, "Delete inventory item soft-deletes")
def test_soft_delete():
    pass


@scenario(FEATURE, "History for item with no actions")
def test_empty_history():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Helpers ---


def _create_item(api, quantity=10, expiry_date=None):
    """Create a vendor, product, inventory item triple."""
    seq = next(_seq)
    r = api.post("/api/v1/vendors", json={"name": f"InvEdgeVendor-{seq}"})
    assert r.status_code == 201, r.text
    vendor = r.json()

    r = api.post(
        "/api/v1/products",
        json={
            "name": f"InvEdgeProduct-{seq}",
            "catalog_number": f"IEDGE-{seq:05d}",
            "vendor_id": vendor["id"],
        },
    )
    assert r.status_code == 201, r.text
    product = r.json()

    payload = {
        "product_id": product["id"],
        "quantity_on_hand": float(quantity),
        "unit": "bottle",
        "lot_number": f"LOT-IEDGE-{seq}",
    }
    if expiry_date:
        payload["expiry_date"] = expiry_date.isoformat()

    r = api.post("/api/v1/inventory", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# --- Given steps ---


@given(
    parsers.parse("an inventory test item with quantity {qty:d} exists"),
    target_fixture="inv_item",
)
def create_inv_item(api, qty):
    return _create_item(api, quantity=qty)


@given("the test item has been opened")
def open_item(api, inv_item):
    r = api.post(
        f"/api/v1/inventory/{inv_item['id']}/open",
        json={"opened_by": "Robert"},
    )
    assert r.status_code == 200, r.text


@given("the test item has been disposed")
def dispose_item(api, inv_item):
    r = api.post(
        f"/api/v1/inventory/{inv_item['id']}/dispose",
        json={"reason": "Test dispose", "disposed_by": "Robert"},
    )
    assert r.status_code == 200, r.text


@given(parsers.parse("{n:d} inventory test items exist"))
def create_n_items(api, n):
    for _ in range(n):
        _create_item(api)


@given("an inventory test item with status available exists")
def create_available_item(api):
    _create_item(api)


@given(
    parsers.parse("an inventory test item expiring in {days:d} days exists"),
    target_fixture="expiring_item",
)
def create_expiring_item(api, days):
    expiry = date.today() + timedelta(days=days)
    return _create_item(api, expiry_date=expiry)


# --- When steps ---


@when(
    parsers.parse("I get inventory item with id {iid:d}"),
    target_fixture="inv_resp",
)
def get_inv_nonexistent(api, iid):
    return api.get(f"/api/v1/inventory/{iid}")


@when(
    parsers.parse("I try to consume {qty:d} from inventory item {iid:d}"),
    target_fixture="inv_resp",
)
def consume_nonexistent(api, qty, iid):
    return api.post(
        f"/api/v1/inventory/{iid}/consume",
        json={"quantity": float(qty), "consumed_by": "Robert"},
    )


@when(
    parsers.parse("I try to consume {qty:d} from the test item"),
    target_fixture="inv_resp",
)
def consume_from_test_item(api, inv_item, qty):
    return api.post(
        f"/api/v1/inventory/{inv_item['id']}/consume",
        json={"quantity": float(qty), "consumed_by": "Robert"},
    )


@when(
    parsers.parse("I try to adjust the test item to {qty:d}"),
    target_fixture="inv_resp",
)
def adjust_test_item(api, inv_item, qty):
    return api.post(
        f"/api/v1/inventory/{inv_item['id']}/adjust",
        json={
            "new_quantity": float(qty),
            "reason": "Test adjust",
            "adjusted_by": "Robert",
        },
    )


@when("I try to open the test item again", target_fixture="inv_resp")
def open_test_item_again(api, inv_item):
    return api.post(
        f"/api/v1/inventory/{inv_item['id']}/open",
        json={"opened_by": "Robert"},
    )


@when("I list all inventory items", target_fixture="inv_list")
def list_all_inventory(api):
    r = api.get("/api/v1/inventory")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I list inventory items with status {status}"),
    target_fixture="inv_list",
)
def list_inventory_by_status(api, status):
    r = api.get("/api/v1/inventory", params={"status": status})
    assert r.status_code == 200, r.text
    return r.json()


@when("I request low stock report", target_fixture="low_stock_resp")
def request_low_stock(api):
    r = api.get("/api/v1/inventory/low-stock")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I request items expiring within {days:d} days"),
    target_fixture="expiring_resp",
)
def request_expiring(api, days):
    r = api.get("/api/v1/inventory/expiring", params={"days": days})
    assert r.status_code == 200, r.text
    return r.json()


@when("I delete the inventory test item", target_fixture="inv_resp")
def delete_inv_item(api, inv_item):
    return api.delete(f"/api/v1/inventory/{inv_item['id']}")


@when("I get history for the test item", target_fixture="history_resp")
def get_item_history(api, inv_item):
    r = api.get(f"/api/v1/inventory/{inv_item['id']}/history")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse("the inventory response status should be {code:d}"))
def check_inv_status(inv_resp, code):
    assert inv_resp.status_code == code


@then(parsers.parse("I should see at least {n:d} inventory items"))
def check_inv_list_min(inv_list, n):
    assert inv_list["total"] >= n


@then(parsers.parse("all listed items should have status {status}"))
def check_all_status(inv_list, status):
    for item in inv_list["items"]:
        assert item["status"] == status


@then("the low stock response should be a list")
def check_low_stock_list(low_stock_resp):
    assert isinstance(low_stock_resp, list)


@then("the expiring items list should not be empty")
def check_expiring_not_empty(expiring_resp):
    assert len(expiring_resp) > 0


@then(parsers.parse("the inventory delete response should be {code:d}"))
def check_inv_delete(inv_resp, code):
    assert inv_resp.status_code == code


@then("the history should be a list")
def check_history_list(history_resp):
    assert isinstance(history_resp, list)
