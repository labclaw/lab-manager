"""Step definitions for vendor management BDD scenarios."""

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/vendors.feature"


# --- Scenarios ---


@scenario(FEATURE, "Create a new vendor with minimal info")
def test_create_vendor_minimal():
    pass


@scenario(FEATURE, "Create a vendor with full details")
def test_create_vendor_full():
    pass


@scenario(FEATURE, "Get vendor by id")
def test_get_vendor():
    pass


@scenario(FEATURE, "Get non-existent vendor returns 404")
def test_get_nonexistent_vendor():
    pass


@scenario(FEATURE, "List vendors returns paginated results")
def test_list_vendors():
    pass


@scenario(FEATURE, "Search vendors by name")
def test_search_vendors():
    pass


@scenario(FEATURE, "Update vendor details")
def test_update_vendor():
    pass


@scenario(FEATURE, "Delete vendor with no references")
def test_delete_vendor():
    pass


@scenario(FEATURE, "Delete vendor with linked products succeeds (soft delete)")
def test_delete_vendor_linked():
    pass


@scenario(FEATURE, "List products for a vendor")
def test_list_vendor_products():
    pass


@scenario(FEATURE, "List orders for a vendor")
def test_list_vendor_orders():
    pass


@scenario(FEATURE, "List vendors when database is empty")
def test_list_vendors_empty():
    pass


@scenario(FEATURE, "Vendor name with special characters")
def test_vendor_special_chars():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# --- Helpers ---


def _table_to_dicts(datatable):
    headers = [str(h).strip() for h in datatable[0]]
    return [
        {headers[i]: str(cell).strip() for i, cell in enumerate(row)}
        for row in datatable[1:]
    ]


# --- Given steps ---


@given(
    parsers.parse('a vendor "{name}" exists in the system'),
    target_fixture="vendor",
)
def create_vendor_given(api, name):
    r = api.post("/api/vendors/", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


@given(
    "the following vendors exist:",
    target_fixture="vendor_list",
)
def create_vendors_from_table(api, datatable):
    rows = _table_to_dicts(datatable)
    vendors = []
    for row in rows:
        r = api.post("/api/vendors/", json={"name": row["name"]})
        assert r.status_code == 201, r.text
        vendors.append(r.json())
    return vendors


@given("a product linked to that vendor exists")
def create_linked_product(api, vendor):
    r = api.post(
        "/api/products/",
        json={
            "name": "Linked Product",
            "catalog_number": "LP-001",
            "vendor_id": vendor["id"],
        },
    )
    assert r.status_code == 201, r.text


@given(parsers.parse('{n:d} products linked to "{name}" exist'))
def create_n_products(api, vendor, n):
    for i in range(n):
        r = api.post(
            "/api/products/",
            json={
                "name": f"Product {i + 1}",
                "catalog_number": f"VPROD-{i + 1:03d}",
                "vendor_id": vendor["id"],
            },
        )
        assert r.status_code == 201, r.text


@given(parsers.parse('{n:d} orders linked to "{name}" exist'))
def create_n_orders(api, vendor, n):
    for i in range(n):
        r = api.post(
            "/api/orders/",
            json={
                "vendor_id": vendor["id"],
                "po_number": f"PO-VORD-{i + 1:03d}",
                "status": "pending",
            },
        )
        assert r.status_code == 201, r.text


# --- When steps ---


@when(
    parsers.parse('I create a vendor with name "{name}"'),
    target_fixture="create_response",
)
def create_vendor_when(api, name):
    r = api.post("/api/vendors/", json={"name": name})
    return r


@when("I create a vendor with:", target_fixture="create_response")
def create_vendor_full(api, datatable):
    rows = _table_to_dicts(datatable)
    payload = {row["field"]: row["value"] for row in rows}
    r = api.post("/api/vendors/", json=payload)
    return r


@when("I get the vendor by id", target_fixture="action_response")
def get_vendor_by_id(api, vendor):
    r = api.get(f"/api/vendors/{vendor['id']}")
    return r


@when(parsers.parse("I get vendor with id {vid:d}"), target_fixture="action_response")
def get_vendor_nonexistent(api, vid):
    r = api.get(f"/api/vendors/{vid}")
    return r


@when("I list all vendors", target_fixture="list_response")
def list_all_vendors(api):
    r = api.get("/api/vendors/")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I search vendors with query "{query}"'),
    target_fixture="list_response",
)
def search_vendors(api, query):
    r = api.get("/api/vendors/", params={"search": query})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I update the vendor name to "{name}"'),
    target_fixture="action_response",
)
def update_vendor(api, vendor, name):
    r = api.patch(f"/api/vendors/{vendor['id']}", json={"name": name})
    assert r.status_code == 200, r.text
    return r


@when("I delete the vendor", target_fixture="delete_response")
def delete_vendor(api, vendor):
    r = api.delete(f"/api/vendors/{vendor['id']}")
    return r


@when("I try to delete the vendor", target_fixture="action_response")
def try_delete_vendor(api, vendor):
    r = api.delete(f"/api/vendors/{vendor['id']}")
    return r


@when("I list products for the vendor", target_fixture="linked_response")
def list_vendor_products(api, vendor):
    r = api.get(f"/api/vendors/{vendor['id']}/products")
    assert r.status_code == 200, r.text
    return r.json()


@when("I list orders for the vendor", target_fixture="linked_response")
def list_vendor_orders(api, vendor):
    r = api.get(f"/api/vendors/{vendor['id']}/orders")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse('the vendor should be created with name "{name}"'))
def check_vendor_created(create_response, name):
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["name"] == name


@then("the vendor should have a valid id")
def check_vendor_id(create_response):
    assert create_response.json()["id"] > 0


@then(parsers.parse('the vendor website should be "{website}"'))
def check_vendor_website(create_response, website):
    assert create_response.json()["website"] == website


@then("I should receive the vendor details")
def check_vendor_details(action_response):
    assert action_response.status_code == 200


@then(parsers.parse('the vendor name should be "{name}"'))
def check_vendor_name_then(action_response, name):
    data = action_response.json()
    assert data["name"] == name


@then(parsers.parse("the response status should be {code:d}"))
def check_response_status(action_response, code):
    assert action_response.status_code == code


@then(parsers.parse("I should see {n:d} vendors in the list"))
def check_vendor_list_count(list_response, n):
    assert list_response["total"] == n


@then("the response should include pagination info")
def check_pagination(list_response):
    assert "page" in list_response
    assert "page_size" in list_response
    assert "pages" in list_response
    assert "total" in list_response


@then(parsers.parse("the delete response status should be {code:d}"))
def check_delete_status(delete_response, code):
    assert delete_response.status_code == code


@then("the vendor should no longer exist")
def check_vendor_deleted(api, vendor):
    r = api.get(f"/api/vendors/{vendor['id']}")
    assert r.status_code == 404


@then(parsers.parse("I should see {n:d} products"))
def check_product_count(linked_response, n):
    assert linked_response["total"] == n


@then(parsers.parse("I should see {n:d} orders"))
def check_order_count(linked_response, n):
    assert linked_response["total"] == n
