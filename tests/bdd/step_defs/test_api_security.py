"""Step definitions for API security feature tests."""

from __future__ import annotations

import io

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/api_security.feature"


@scenario(FEATURE, "SQL injection in product name")
def test_sql_injection_product_name():
    pass


@scenario(FEATURE, "SQL injection in search query")
def test_sql_injection_search():
    pass


@scenario(FEATURE, "HTML characters in vendor name round-trip safely")
def test_html_vendor_name():
    pass


@scenario(FEATURE, "HTML characters in product metadata round-trip safely")
def test_html_product_metadata():
    pass


@scenario(FEATURE, "Path traversal in document path is rejected")
def test_path_traversal():
    pass


@scenario(FEATURE, "Upload exceeds size limit")
def test_upload_size_limit():
    pass


@scenario(FEATURE, "Request body too large")
def test_request_body_size():
    pass


@scenario(FEATURE, "Invalid product identifier in path")
def test_invalid_product_identifier():
    pass


@scenario(FEATURE, "Negative quantity")
def test_negative_quantity():
    pass


@scenario(FEATURE, "Quantity exceeds maximum")
def test_quantity_exceeds_max():
    pass


@scenario(FEATURE, "Rate limit exceeded on login")
def test_rate_limit():
    pass


@scenario(FEATURE, "CORS headers on preflight")
def test_cors_preflight():
    pass


@scenario(FEATURE, "Invalid upload content type")
def test_invalid_content_type():
    pass


@given('I am authenticated as staff "user1"')
def authenticated_user(api):
    return api


@given(
    parsers.parse('product metadata contains "{html_text}"'),
    target_fixture="product_metadata",
)
def product_metadata(api, html_text):
    response = api.post(
        "/api/v1/products/",
        json={
            "catalog_number": "META-001",
            "name": "Metadata Product",
            "extra": {"description": html_text},
        },
    )
    assert response.status_code == 201
    return {"id": response.json()["id"], "html_text": html_text}


@given("I have made 5 login attempts in the last minute")
def login_attempts_exhausted(api):
    limiter = getattr(api.app.state, "limiter", None)
    storage = getattr(limiter, "_storage", None) if limiter else None
    reset = getattr(storage, "reset", None) if storage else None
    if callable(reset):
        reset()
    for _ in range(5):
        response = api.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-password"},
        )
        assert response.status_code in (401, 429)


@when(
    parsers.parse('I create a product with name "{name}"'),
    target_fixture="product_response",
)
def create_product_with_name(api, name):
    response = api.post(
        "/api/v1/products/",
        json={"name": name, "catalog_number": "CAT-001"},
    )
    return response


@when(
    parsers.parse('I create a vendor with name "{name}"'),
    target_fixture="vendor_response",
)
def create_vendor_with_name(api, name):
    response = api.post("/api/v1/vendors/", json={"name": name})
    return response


@when(parsers.parse('I search for "{query}"'), target_fixture="search_response")
def search_query(api, query):
    response = api.get("/api/v1/search", params={"q": query})
    return response


@when(
    parsers.parse('I request product with ID "{pid}"'),
    target_fixture="product_detail_response",
)
def request_product(api, pid):
    response = api.get(f"/api/v1/products/{pid}")
    return response


@when("I request the product details", target_fixture="product_detail_response")
def request_product_details(api, product_metadata):
    response = api.get(f"/api/v1/products/{product_metadata['id']}")
    return response


@when(
    parsers.parse('I create a document with path "{path}"'),
    target_fixture="path_response",
)
def create_document_with_path(api, path):
    response = api.post(
        "/api/v1/documents/",
        json={
            "file_path": path,
            "file_name": "passwd.pdf",
            "status": "pending",
        },
    )
    return response


@when("I upload a file larger than 50MB", target_fixture="upload_response")
def upload_large_file(api):
    content = io.BytesIO(b"x" * (51 * 1024 * 1024))
    response = api.post(
        "/api/v1/documents/upload",
        files={"file": ("large.pdf", content, "application/pdf")},
    )
    return response


@when("I send a JSON body larger than 10MB", target_fixture="large_body_response")
def send_large_json_body(api):
    large_data = {"notes": "x" * (10 * 1024 * 1024 + 1024), "name": "Big Vendor"}
    response = api.post("/api/v1/vendors/", json=large_data)
    return response


@when(
    parsers.parse("I create an order item with quantity {qty:d}"),
    target_fixture="order_item_response",
)
def create_order_item_with_quantity(api, qty):
    vendor_response = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    assert vendor_response.status_code == 201
    order_response = api.post(
        "/api/v1/orders/",
        json={"vendor_id": vendor_response.json()["id"], "po_number": "SEC-001"},
    )
    assert order_response.status_code == 201
    order_id = order_response.json()["id"]
    response = api.post(
        f"/api/v1/orders/{order_id}/items",
        json={"description": "Test Item", "quantity": qty, "unit_price": 10.0},
    )
    return response


@when("I make another login attempt", target_fixture="rate_limited_response")
def make_another_login_attempt(api):
    response = api.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password"},
    )
    return response


@when(
    "I send a proper OPTIONS preflight request",
    target_fixture="cors_preflight_response",
)
def send_options_request(api):
    response = api.options(
        "/api/v1/vendors/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    return response


@when(
    "I upload an XML document to the upload endpoint",
    target_fixture="invalid_upload_response",
)
def upload_invalid_content_type(api):
    response = api.post(
        "/api/v1/documents/upload",
        files={"file": ("payload.xml", io.BytesIO(b"<xml />"), "application/xml")},
    )
    return response


@then("the product should be created with the literal name")
def check_product_created(product_response):
    assert product_response.status_code == 201
    assert product_response.json()["name"] == "'; DROP TABLE products; --"


@then("no SQL injection should occur")
def check_no_sql_injection(api):
    response = api.get("/api/v1/products/")
    assert response.status_code == 200


@then("the search should be sanitized")
def check_search_sanitized(search_response):
    assert search_response.status_code in (200, 400, 422)


@then("no data leak should occur")
def check_no_data_leak(search_response):
    assert search_response.status_code != 500


@then("the vendor name should round-trip as raw text")
def check_vendor_name_raw(vendor_response):
    assert vendor_response.status_code == 201
    assert vendor_response.json()["name"] == "<script>alert('xss')</script>"


@then("the description metadata should round-trip as raw text")
def check_description_metadata_raw(product_detail_response, product_metadata):
    assert product_detail_response.status_code == 200
    assert (
        product_detail_response.json()["extra"]["description"]
        == product_metadata["html_text"]
    )


@then("the response should be safe JSON")
def check_safe_json_response(request):
    candidate = None
    for fixture_name in (
        "vendor_response",
        "product_detail_response",
        "product_response",
    ):
        if fixture_name in request.fixturenames:
            candidate = request.getfixturevalue(fixture_name)
            break
    assert candidate is not None
    assert "application/json" in candidate.headers.get("content-type", "")


@then("the request should be rejected")
def check_path_rejected(path_response):
    assert path_response.status_code in (400, 403, 422)


@then("no file system access should occur")
def check_no_filesystem_access(path_response):
    assert "traversal" in str(path_response.json()).lower()


@then("I should receive a 413 Payload Too Large error")
def check_payload_too_large(upload_response):
    assert upload_response.status_code == 413


@then("the error should indicate size limit")
def check_size_limit_error(upload_response):
    detail = str(upload_response.json()).lower()
    assert "size" in detail or "limit" in detail or "maximum" in detail


@then("I should receive a 413 error")
def check_large_body_error(large_body_response):
    assert large_body_response.status_code == 413


@then("memory should not be exhausted")
def check_memory_not_exhausted(large_body_response):
    assert large_body_response.status_code == 413


@then("I should receive a 422 validation error")
def check_validation_error_path(product_detail_response):
    assert product_detail_response.status_code == 422


@then("the error should specify integer format")
def check_integer_format_error(product_detail_response):
    assert "int" in str(product_detail_response.json()).lower()


@then("I should receive a validation error")
def check_validation_error(order_item_response):
    assert order_item_response.status_code == 422


@then("the error should indicate minimum value")
def check_minimum_value_error(order_item_response):
    assert "greater than 0" in str(order_item_response.json()).lower()


@then("the error should indicate maximum value")
def check_maximum_value_error(order_item_response):
    assert "less than or equal to" in str(order_item_response.json()).lower()


@then("I should receive a 429 Too Many Requests error")
def check_rate_limit_error(rate_limited_response):
    assert rate_limited_response.status_code == 429


@then("the response should include retry-after header")
def check_retry_after_header(rate_limited_response):
    assert rate_limited_response.headers.get("Retry-After") == "60"


@then("appropriate CORS headers should be returned")
def check_cors_headers(cors_preflight_response):
    assert cors_preflight_response.status_code == 200
    headers = {k.lower(): v for k, v in cors_preflight_response.headers.items()}
    assert "access-control-allow-origin" in headers


@then("allowed methods should be listed")
def check_allowed_methods(cors_preflight_response):
    methods = cors_preflight_response.headers.get("Access-Control-Allow-Methods", "")
    assert "GET" in methods


@then("I should receive a 400 error")
def check_bad_request(invalid_upload_response):
    assert invalid_upload_response.status_code == 400


@then("the error should indicate unsupported file type")
def check_unsupported_media_type(invalid_upload_response):
    assert "not allowed" in str(invalid_upload_response.json()).lower()
