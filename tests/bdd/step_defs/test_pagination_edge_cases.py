"""BDD step definitions for pagination edge cases."""
import pytest
from pytest_bdd import given, when, then, scenarios, parsers

scenarios("../features/pagination_edge_cases.feature")


# --- Shared context fixture ---
@pytest.fixture
def ctx():
    """Shared context for storing responses between steps."""
    return {}


# --- Background steps ---

@given("the system is set up")
def system_setup(api):
    """Ensure system is set up."""
    r = api.get("/api/setup/status")
    if r.status_code == 200 and r.json().get("needs_setup"):
        api.post(
            "/api/setup/complete",
            json={
                "admin_name": "Test Admin",
                "admin_email": "admin@test.com",
                "admin_password": "TestPassword123!",
            },
        )


@given('I am logged in as "admin@test.com"')
def logged_in(api):
    """Log in as admin user."""
    api.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "TestPassword123!"},
    )


# --- Given steps ---

@given("300 documents exist")
def three_hundred_documents(db):
    """Create 300 test documents."""
    from lab_manager.models.document import Document
    for i in range(300):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db.add(doc)
    db.commit()


@given("50 documents exist")
def fifty_documents(db):
    """Create 50 test documents."""
    from lab_manager.models.document import Document
    for i in range(50):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db.add(doc)
    db.commit()


@given("10 documents exist")
def ten_documents(db):
    """Create 10 test documents."""
    from lab_manager.models.document import Document
    for i in range(10):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db.add(doc)
    db.commit()


@given("100 documents exist with various statuses")
def documents_various_statuses(db):
    """Create documents with different statuses."""
    from lab_manager.models.document import Document
    statuses = ["approved", "needs_review", "rejected", "approved", "needs_review"]
    for i in range(100):
        doc = Document(
            file_name=f"test_{i}.pdf",
            status=statuses[i % len(statuses)]
        )
        db.add(doc)
    db.commit()


# --- When steps ---

@when("I request the documents list without parameters", target_fixture="response")
def request_documents_default(api):
    """Request documents with default pagination."""
    return api.get("/api/v1/documents/")


@when(parsers.parse('I request the documents list with page_size {size:d}'), target_fixture="response")
def request_documents_page_size(api, size):
    """Request documents with specific page size."""
    return api.get(f"/api/v1/documents/?page_size={size}")


@when(parsers.parse('I request the documents list with page {page:d}'), target_fixture="response")
def request_documents_page(api, page):
    """Request documents at specific page."""
    return api.get(f"/api/v1/documents/?page={page}")


@when('I request documents with status "needs_review" and page 2', target_fixture="response")
def request_documents_filtered(api):
    """Request filtered documents."""
    return api.get("/api/v1/documents/?status=needs_review&page=2&page_size=20")


@when("I request each list endpoint with pagination")
def request_all_list_endpoints(api, ctx):
    """Request all list endpoints."""
    endpoints = [
        "/api/v1/vendors/",
        "/api/v1/products/",
        "/api/v1/orders/",
        "/api/v1/inventory/",
        "/api/v1/documents/",
        "/api/v1/alerts/",
    ]
    ctx["responses"] = {}
    for endpoint in endpoints:
        ctx["responses"][endpoint] = api.get(f"{endpoint}?page=1&page_size=20")


# --- Then steps ---

@then(parsers.parse("the response should contain {count:d} items"))
def response_contains_items(response, count):
    """Verify response item count."""
    data = response.json()
    actual = len(data.get("items", []))
    assert actual == count, f"Expected {count} items, got {actual}"


@then("page should be 1")
def page_is_one(response):
    """Verify page is 1."""
    assert response.json().get("page") == 1


@then("page_size should be 20")
def page_size_is_twenty(response):
    """Verify page_size is 20."""
    assert response.json().get("page_size") == 20


@then(parsers.parse("total should be {count:d}"))
def total_is_count(response, count):
    """Verify total count."""
    assert response.json().get("total") == count


@then(parsers.parse("pages should be {count:d}"))
def pages_is_count(response, count):
    """Verify page count."""
    assert response.json().get("pages") == count


@then("the response should be 422 Unprocessable Entity")
def response_is_422(response):
    """Verify 422 response."""
    assert response.status_code == 422


@then('the error should mention "page_size"')
def error_mentions_page_size(response):
    """Verify error mentions page_size."""
    data = response.json()
    assert "page_size" in str(data).lower()


@then("the response should contain 0 items")
def response_contains_zero(response):
    """Verify empty response."""
    data = response.json()
    assert len(data.get("items", [])) == 0


@then("total should still be 50")
def total_still_fifty(response):
    """Verify total preserved."""
    assert response.json().get("total") == 50


@then("only documents with status \"needs_review\" should be returned")
def only_needs_review(response):
    """Verify filtered results."""
    data = response.json()
    for item in data.get("items", []):
        assert item.get("status") == "needs_review"


@then("pagination should reflect filtered count")
def pagination_reflects_filter(response):
    """Verify pagination with filter."""
    data = response.json()
    # Total should be less than 100 due to filter
    assert data.get("total") < 100


@then("all should return paginated responses")
def all_paginated(ctx):
    """Verify all responses are paginated."""
    responses = ctx.get("responses", {})
    for endpoint, resp in responses.items():
        assert resp.status_code == 200, f"{endpoint} failed"
        data = resp.json()
        assert "items" in data, f"{endpoint} missing items"
        assert "total" in data, f"{endpoint} missing total"
        assert "page" in data, f"{endpoint} missing page"
        assert "pages" in data, f"{endpoint} missing pages"


@then("the response should be paginated")
def response_is_paginated(response):
    """Verify response has pagination fields."""
    data = response.json()
    assert all(k in data for k in ["items", "total", "page", "page_size", "pages"])


@given(parsers.parse("{count:d} {resource} exist"))
def create_resource(db, count, resource):
    """Create test resources."""
    from lab_manager.models.document import Document
    from lab_manager.models.vendor import Vendor
    from lab_manager.models.alert import Alert
    
    for i in range(count):
        if resource == "vendors":
            obj = Vendor(name=f"Vendor {i}")
        elif resource == "documents":
            obj = Document(file_name=f"doc_{i}.pdf", status="approved")
        elif resource == "alerts":
            obj = Alert(type="test", message=f"Alert {i}", severity="info")
        else:
            continue  # Skip unsupported resources
        db.add(obj)
    db.commit()


@when(parsers.parse("I request the {resource} list"), target_fixture="response")
def request_resource_list(api, resource):
    """Request a resource list."""
    endpoints = {
        "vendors": "/api/v1/vendors/",
        "products": "/api/v1/products/",
        "orders": "/api/v1/orders/",
        "inventory": "/api/v1/inventory/",
        "documents": "/api/v1/documents/",
        "alerts": "/api/v1/alerts/",
    }
    return api.get(endpoints.get(resource, "/api/v1/documents/"))
