"""Step definitions for product management BDD scenarios."""

import itertools

import pytest
from conftest import table_to_dicts as _table_to_dicts
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/products.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Create a product with required fields")
def test_create_product():
    pass


@scenario(FEATURE, "Create a product with CAS number")
def test_create_product_cas():
    pass


@scenario(FEATURE, "Reject product with invalid CAS number format")
def test_reject_invalid_cas():
    pass


@scenario(FEATURE, "Reject product with empty name")
def test_reject_empty_name():
    pass


@scenario(FEATURE, "Get product by id")
def test_get_product():
    pass


@scenario(FEATURE, "Get non-existent product returns 404")
def test_get_nonexistent_product():
    pass


@scenario(FEATURE, "List products with vendor filter")
def test_list_products_vendor_filter():
    pass


@scenario(FEATURE, "Search products by name")
def test_search_products():
    pass


@scenario(FEATURE, "Update product name")
def test_update_product():
    pass


@scenario(FEATURE, "Delete a product")
def test_delete_product():
    pass


@scenario(FEATURE, "List inventory for a product")
def test_list_product_inventory():
    pass


@scenario(FEATURE, "List order items for a product")
def test_list_product_orders():
    pass


@scenario(FEATURE, "Product with max length name")
def test_max_length_name():
    pass


@scenario(FEATURE, "List products when none exist for vendor")
def test_list_empty_products():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Helpers ---


# --- Given steps ---


@given(
    parsers.parse('a vendor "{name}" exists for products'),
    target_fixture="prd_vendor",
)
def create_vendor_for_products(api, ctx, name):
    r = api.post("/api/v1/vendors", json={"name": name})
    assert r.status_code == 201, r.text
    v = r.json()
    ctx.setdefault("vendors", {})[name] = v
    return v


@given(
    parsers.parse('a product "{name}" with catalog "{catalog}" exists'),
    target_fixture="product",
)
def create_product_given(api, prd_vendor, name, catalog):
    r = api.post(
        "/api/v1/products",
        json={
            "name": name,
            "catalog_number": catalog,
            "vendor_id": prd_vendor["id"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@given(parsers.parse('{n:d} products exist for "{vendor_name}"'))
def create_n_products_for_vendor(api, ctx, n, vendor_name):
    v = ctx["vendors"][vendor_name]
    for i in range(n):
        seq = next(_seq)
        r = api.post(
            "/api/v1/products",
            json={
                "name": f"Product {seq}",
                "catalog_number": f"PCAT-{seq:05d}",
                "vendor_id": v["id"],
            },
        )
        assert r.status_code == 201, r.text


@given("the following products exist for search:")
def create_products_for_search(api, prd_vendor, datatable):
    rows = _table_to_dicts(datatable)
    for row in rows:
        r = api.post(
            "/api/v1/products",
            json={
                "name": row["name"],
                "catalog_number": row["catalog"],
                "vendor_id": prd_vendor["id"],
            },
        )
        assert r.status_code == 201, r.text


@given(parsers.parse("{n:d} inventory items exist for the product"))
def create_inventory_for_product(api, product, n):
    for i in range(n):
        r = api.post(
            "/api/v1/inventory",
            json={
                "product_id": product["id"],
                "quantity_on_hand": 10,
                "unit": "bottle",
                "lot_number": f"LOT-PINV-{i + 1}",
            },
        )
        assert r.status_code == 201, r.text


@given(parsers.parse("{n:d} order items reference the product"))
def create_order_items_for_product(api, prd_vendor, product, n):
    for i in range(n):
        # Create an order first
        r = api.post(
            "/api/v1/orders",
            json={
                "vendor_id": prd_vendor["id"],
                "po_number": f"PO-PORD-{next(_seq)}",
                "status": "pending",
            },
        )
        assert r.status_code == 201, r.text
        order = r.json()
        # Add item referencing the product
        r = api.post(
            f"/api/v1/orders/{order['id']}/items",
            json={
                "product_id": product["id"],
                "catalog_number": product["catalog_number"],
                "description": product["name"],
                "quantity": 1,
                "unit": "EA",
            },
        )
        assert r.status_code == 201, r.text


# --- When steps ---


@when(
    parsers.parse('I create a product with name "{name}" catalog "{catalog}"'),
    target_fixture="prd_response",
)
def create_product_when(api, prd_vendor, name, catalog):
    r = api.post(
        "/api/v1/products",
        json={
            "name": name,
            "catalog_number": catalog,
            "vendor_id": prd_vendor["id"],
        },
    )
    return r


@when(
    parsers.parse(
        'I create a product with name "{name}" catalog "{catalog}" and CAS "{cas}"'
    ),
    target_fixture="prd_response",
)
def create_product_with_cas(api, prd_vendor, name, catalog, cas):
    r = api.post(
        "/api/v1/products",
        json={
            "name": name,
            "catalog_number": catalog,
            "vendor_id": prd_vendor["id"],
            "cas_number": cas,
        },
    )
    return r


@when(
    parsers.parse('I try to create a product with invalid CAS "{cas}"'),
    target_fixture="prd_response",
)
def create_product_invalid_cas(api, prd_vendor, cas):
    r = api.post(
        "/api/v1/products",
        json={
            "name": "Bad CAS Product",
            "catalog_number": f"BADCAS-{next(_seq)}",
            "vendor_id": prd_vendor["id"],
            "cas_number": cas,
        },
    )
    return r


@when(
    "I try to create a product with empty name",
    target_fixture="prd_response",
)
def create_product_empty_name(api, prd_vendor):
    r = api.post(
        "/api/v1/products",
        json={
            "name": "",
            "catalog_number": f"EMPTY-{next(_seq)}",
            "vendor_id": prd_vendor["id"],
        },
    )
    return r


@when("I get the product by id", target_fixture="prd_detail")
def get_product_by_id(api, product):
    r = api.get(f"/api/v1/products/{product['id']}")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse("I get product with id {pid:d}"),
    target_fixture="prd_response",
)
def get_product_nonexistent(api, pid):
    return api.get(f"/api/v1/products/{pid}")


@when(
    parsers.parse('I list products for vendor "{vendor_name}"'),
    target_fixture="prd_list",
)
def list_products_for_vendor(api, ctx, vendor_name):
    v = ctx["vendors"][vendor_name]
    r = api.get("/api/v1/products", params={"vendor_id": v["id"]})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I search products with query "{query}"'),
    target_fixture="prd_list",
)
def search_products(api, query):
    r = api.get("/api/v1/products", params={"search": query})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I update the product name to "{name}"'),
    target_fixture="prd_detail",
)
def update_product_name(api, product, name):
    r = api.patch(f"/api/v1/products/{product['id']}", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


@when("I delete the product", target_fixture="prd_response")
def delete_product(api, product):
    return api.delete(f"/api/v1/products/{product['id']}")


@when("I list inventory for the product", target_fixture="prd_linked_list")
def list_product_inventory(api, product):
    r = api.get(f"/api/v1/products/{product['id']}/inventory")
    assert r.status_code == 200, r.text
    return r.json()


@when("I list orders for the product", target_fixture="prd_linked_list")
def list_product_orders(api, product):
    r = api.get(f"/api/v1/products/{product['id']}/orders")
    assert r.status_code == 200, r.text
    return r.json()


@when("I create a product with a 500-character name", target_fixture="prd_response")
def create_product_max_name(api, prd_vendor):
    long_name = "A" * 500
    r = api.post(
        "/api/v1/products",
        json={
            "name": long_name,
            "catalog_number": f"MAXNAME-{next(_seq)}",
            "vendor_id": prd_vendor["id"],
        },
    )
    return r


# --- Then steps ---


@then("the product should be created successfully")
def check_product_created(prd_response):
    assert prd_response.status_code == 201, prd_response.text


@then(parsers.parse('the product name should be "{name}"'))
def check_product_name(prd_response, name):
    assert prd_response.json()["name"] == name


@then(parsers.parse('the product catalog_number should be "{catalog}"'))
def check_product_catalog(prd_response, catalog):
    assert prd_response.json()["catalog_number"] == catalog


@then(parsers.parse('the product cas_number should be "{cas}"'))
def check_product_cas(prd_response, cas):
    assert prd_response.json()["cas_number"] == cas


@then(parsers.parse("the product create response status should be {code:d}"))
def check_product_create_status(prd_response, code):
    assert prd_response.status_code == code


@then(parsers.parse("the product response status should be {code:d}"))
def check_product_response_status(prd_response, code):
    assert prd_response.status_code == code


@then(parsers.parse('the product detail name should be "{name}"'))
def check_product_detail_name(prd_detail, name):
    assert prd_detail["name"] == name


@then(parsers.parse("I should see {n:d} products in the product list"))
def check_product_list_count(prd_list, n):
    assert prd_list["total"] == n


@then(parsers.parse("the product delete response should be {code:d}"))
def check_product_delete_status(prd_response, code):
    assert prd_response.status_code == code


@then(parsers.parse("I should see {n:d} items in the product inventory"))
def check_product_inventory_count(prd_linked_list, n):
    assert prd_linked_list["total"] == n


@then(parsers.parse("I should see {n:d} items in the product orders"))
def check_product_orders_count(prd_linked_list, n):
    assert prd_linked_list["total"] == n
