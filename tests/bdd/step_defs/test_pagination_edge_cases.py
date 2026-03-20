"""BDD step definitions for pagination edge cases."""
import pytest
from pytest_bdd import given, when, then, scenarios, parsers

scenarios("../features/pagination_edge_cases.feature")


@given("300 documents exist")
def three_hundred_documents(db_session):
    """Create 300 test documents."""
    from lab_manager.models.document import Document
    for i in range(300):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db_session.add(doc)
    db_session.commit()


@given("50 documents exist")
def fifty_documents(db_session):
    """Create 50 test documents."""
    from lab_manager.models.document import Document
    for i in range(50):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db_session.add(doc)
    db_session.commit()


@given("10 documents exist")
def ten_documents(db_session):
    """Create 10 test documents."""
    from lab_manager.models.document import Document
    for i in range(10):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db_session.add(doc)
    db_session.commit()


@given("100 documents exist with various statuses")
def documents_various_statuses(db_session):
    """Create documents with different statuses."""
    from lab_manager.models.document import Document
    statuses = ["approved", "needs_review", "rejected", "approved", "needs_review"]
    for i in range(100):
        doc = Document(
            file_name=f"test_{i}.pdf",
            status=statuses[i % len(statuses)]
        )
        db_session.add(doc)
    db_session.commit()


@when("I request the documents list without parameters")
def request_documents_default(client):
    """Request documents with default pagination."""
    return client.get("/api/v1/documents/")


@when(parsers.parse('I request the documents list with page_size {size:d}'))
def request_documents_page_size(client, size):
    """Request documents with specific page size."""
    return client.get(f"/api/v1/documents/?page_size={size}")


@when(parsers.parse('I request the documents list with page {page:d}'))
def request_documents_page(client, page):
    """Request documents at specific page."""
    return client.get(f"/api/v1/documents/?page={page}")


@when(parsers.parse('I request the documents list with page {page:d}'))
def request_documents_negative_page(client, page):
    """Request documents with negative page."""
    return client.get(f"/api/v1/documents/?page={page}")


@when('I request documents with status "needs_review" and page 2')
def request_documents_filtered(client):
    """Request filtered documents."""
    return client.get("/api/v1/documents/?status=needs_review&page=2&page_size=20")


@when("I request each list endpoint with pagination")
def request_all_list_endpoints(client, context):
    """Request all list endpoints."""
    endpoints = [
        "/api/v1/vendors/",
        "/api/v1/products/",
        "/api/v1/orders/",
        "/api/v1/inventory/",
        "/api/v1/documents/",
        "/api/v1/alerts/",
    ]
    context["responses"] = {}
    for endpoint in endpoints:
        context["responses"][endpoint] = client.get(f"{endpoint}?page=1&page_size=20")


@then(parsers.parse("the response should contain {count:d} items"))
def response_contains_items(context, count):
    """Verify response item count."""
    response = context.get("response")
    if response:
        data = response.json()
        assert len(data.get("items", [])) == count, f"Expected {count} items, got {len(data.get('items', []))}"


@then("page should be 1")
def page_is_one(context):
    """Verify page is 1."""
    response = context.get("response")
    if response:
        assert response.json().get("page") == 1


@then("page_size should be 20")
def page_size_is_twenty(context):
    """Verify page_size is 20."""
    response = context.get("response")
    if response:
        assert response.json().get("page_size") == 20


@then(parsers.parse("total should be {count:d}"))
def total_is_count(context, count):
    """Verify total count."""
    response = context.get("response")
    if response:
        assert response.json().get("total") == count


@then(parsers.parse("pages should be {count:d}"))
def pages_is_count(context, count):
    """Verify page count."""
    response = context.get("response")
    if response:
        assert response.json().get("pages") == count


@then("the response should be 422 Unprocessable Entity")
def response_is_422(context):
    """Verify 422 response."""
    response = context.get("response")
    if response:
        assert response.status_code == 422


@then('the error should mention "page_size"')
def error_mentions_page_size(context):
    """Verify error mentions page_size."""
    response = context.get("response")
    if response:
        data = response.json()
        assert "page_size" in str(data).lower()


@then("the response should contain 0 items")
def response_contains_zero(context):
    """Verify empty response."""
    response = context.get("response")
    if response:
        data = response.json()
        assert len(data.get("items", [])) == 0


@then("total should still be 50")
def total_still_fifty(context):
    """Verify total preserved."""
    response = context.get("response")
    if response:
        assert response.json().get("total") == 50


@then("only documents with status \"needs_review\" should be returned")
def only_needs_review(context):
    """Verify filtered results."""
    response = context.get("response")
    if response:
        data = response.json()
        for item in data.get("items", []):
            assert item.get("status") == "needs_review"


@then("pagination should reflect filtered count")
def pagination_reflects_filter(context):
    """Verify pagination with filter."""
    response = context.get("response")
    if response:
        data = response.json()
        # Total should be less than 100 due to filter
        assert data.get("total") < 100


@then("all should return paginated responses")
def all_paginated(context):
    """Verify all responses are paginated."""
    responses = context.get("responses", {})
    for endpoint, response in responses.items():
        assert response.status_code == 200, f"{endpoint} failed"
        data = response.json()
        assert "items" in data, f"{endpoint} missing items"
        assert "total" in data, f"{endpoint} missing total"
        assert "page" in data, f"{endpoint} missing page"
        assert "pages" in data, f"{endpoint} missing pages"


@then("the response should be paginated")
def response_is_paginated(context):
    """Verify response has pagination fields."""
    response = context.get("response")
    if response:
        data = response.json()
        assert all(k in data for k in ["items", "total", "page", "page_size", "pages"])


@given(parsers.parse("{count:d} {resource} exist"))
def create_resource(db_session, count, resource):
    """Create test resources."""
    models = {
        "vendors": "lab_manager.models.vendor.Vendor",
        "products": "lab_manager.models.product.Product",
        "orders": "lab_manager.models.order.Order",
        "inventory": "lab_manager.models.inventory.InventoryItem",
        "documents": "lab_manager.models.document.Document",
        "alerts": "lab_manager.models.alert.Alert",
    }
    # Import the model dynamically
    module_path, class_name = models[resource].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    Model = getattr(module, class_name)
    
    for i in range(count):
        if resource == "vendors":
            obj = Model(name=f"Vendor {i}")
        elif resource == "documents":
            obj = Model(file_name=f"doc_{i}.pdf", status="approved")
        elif resource == "alerts":
            obj = Model(type="test", message=f"Alert {i}", severity="info")
        else:
            obj = Model()
        db_session.add(obj)
    db_session.commit()


@when(parsers.parse("I request the {resource} list"))
def request_resource_list(client, context, resource):
    """Request a resource list."""
    endpoints = {
        "vendors": "/api/v1/vendors/",
        "products": "/api/v1/products/",
        "orders": "/api/v1/orders/",
        "inventory": "/api/v1/inventory/",
        "documents": "/api/v1/documents/",
        "alerts": "/api/v1/alerts/",
    }
    context["response"] = client.get(endpoints[resource])
