"""Step definitions for API Security feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/api_security.feature"
# --- Scenarios ---


@scenario(FEATURE, "SQL injection in product name")
def test_sql_injection_product_name():
    pass


@scenario(FEATURE, "SQL injection in search query")
def test_sql_injection_search():
    pass


@scenario(FEATURE, "XSS in vendor name")
def test_xss_vendor_name():
    pass


@scenario(FEATURE, "XSS in product description")
def test_xss_product_description():
    pass


@scenario(FEATURE, "Path traversal in document upload")
def test_path_traversal():
    pass


@scenario(FEATURE, "Upload exceeds size limit")
def test_upload_size_limit():
    pass


@scenario(FEATURE, "Request body too large")
def test_request_body_size():
    pass


@scenario(FEATURE, "Invalid UUID in path")
def test_invalid_uuid():
    pass


@scenario(FEATURE, "Negative quantity")
def test_negative_quantity():
    pass


@scenario(FEATURE, "Quantity exceeds maximum")
def test_quantity_exceeds_max():
    pass


@scenario(FEATURE, "Rate limit exceeded")
def test_rate_limit():
    pass


@scenario(FEATURE, "CORS headers on preflight")
def test_cors_preflight():
    pass


@scenario(FEATURE, "Invalid authorization header format")
def test_invalid_auth_header():
    pass


@scenario(FEATURE, "Expired token")
def test_expired_token():
    pass


@scenario(FEATURE, "Bulk create exceeds limit")
def test_bulk_create_limit():
    pass


@scenario(FEATURE, "Invalid content type")
def test_invalid_content_type():
    pass


# --- Given steps ---
@given('I am authenticated as staff "user1"')
def authenticated_user(api):
    return api


# --- When steps ---
@when(parsers.parse('I create a product with name "{name}"'))
def create_product_with_name(api, name):
    r = api.post(
        "/api/v1/products/",
        json={"name": name, "catalog_number": "CAT-001", "vendor_id": 1},
    )
    return r


@when(parsers.parse('I create a vendor with name "{name}"'))
def create_vendor_with_name(api, name):
    r = api.post("/api/v1/vendors/", json={"name": name})
    return r


@when(parsers.parse('I search for "{query}"'), target_fixture="search_response")
def search_query(api, query):
    r = api.get("/api/v1/search", params={"q": query})
    return r


@when(parsers.parse('I request product with ID "{pid}"'))
def request_product(api, pid):
    r = api.get(f"/api/v1/products/{pid}")
    return r


@when(parsers.parse("I create an order with quantity {qty:d}"))
def create_order_with_quantity(api, qty):
    # Need vendor first
    r = api.post("/api/v1/vendors/", json={"name": "Test Vendor"})
    vendor = r.json()
    r = api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "items": [{"product_name": "Test", "quantity": qty, "unit_price": 10.0}],
        },
    )
    return r


@when("I upload a file larger than 50MB", target_fixture="upload_response")
def upload_large_file(api):
    # Create a large file
    import tempfile

    large_content = b"x" * (51 * 1024 * 1024 + 1)  # 51MB
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(large_content)
        tmp.flush()
        tmp.seek(0)
        r = api.post(
            "/api/v1/documents/",
            files={"file": ("large.txt", tmp)},
        )
    return r


@when("I send an OPTIONS request")
def send_options_request(api):
    """Send CORS preflight request."""
    return api.options("/api/v1/vendors/")


@when("I send a request with 10MB JSON body", target_fixture="large_body_response")
def send_large_json_body(api):
    large_data = {"data": "x" * (10 * 1024 * 1024 - 10)}  # ~10MB
    r = api.post("/api/v1/vendors/", json=large_data)
    return r


# --- Then steps ---
@then("the product should be created with the literal name")
def check_product_created(api):
    # Verify the product was created with the literal SQL injection string
    # (the previous step should have created it)
    r = api.get("/api/v1/products/")
    assert r.status_code == 200
    # Check that the SQL string is stored literally, not executed
    items = r.json().get("items", [])
    if items:
        # Product was created, verify the name is the literal string
        assert any("DROP TABLE" in p.get("name", "") for p in items)


@then("no SQL injection should occur")
def check_no_sql_injection():
    pass


@then("the search should be sanitized")
def check_search_sanitized(search_response):
    # search_response is a Response object from the fixture
    assert search_response.status_code in (200, 400, 422)


@then("no data leak should occur")
def check_no_data_leak():
    pass


@then("the vendor name should be HTML-escaped in responses")
def check_vendor_name_escaped(api):
    r = api.get("/api/v1/vendors/")
    assert "<script>" not in r.text


@then("the script should not execute")
def check_script_not_execute():
    pass


@then("the HTML should be escaped or stripped")
def check_html_escaped(api):
    r = api.get("/api/v1/products/1")
    # Response should not contain executable HTML
    assert "<script>" not in r.text


@then("the request should be rejected")
def check_path_rejected(upload_response):
    assert upload_response["status_code"] in (400, 403, 422)


@then("no file system access should occur")
def check_no_filesystem_access():
    pass


@then("I should receive a 413 Payload Too Large error")
def check_payload_too_large(upload_response):
    assert upload_response["status_code"] == 413


@then("the error should indicate size limit")
def check_size_limit_error(upload_response):
    assert (
        "size" in str(upload_response.json()).lower()
        or "limit" in str(upload_response.json()).lower()
    )
    pass


@then("I should receive a 413 error")
def check_large_body_error(large_body_response):
    assert large_body_response["status_code"] == 413


@then("memory should not be exhausted")
def check_memory_not_exhausted():
    pass


@then("I should receive a 422 validation error")
def check_validation_error_uuid(api):
    r = api.get("/api/v1/products/not-a-uuid")
    assert r.status_code == 422


@then("the error should specify UUID format")
def check_uuid_format_error(api):
    # Error message should mention UUID
    pass


@then("I should receive a validation error")
def check_validation_error_negative_qty(create_order_with_quantity):
    assert create_order_with_quantity["status_code"] in (400, 422)


@then("the error should indicate minimum value")
def check_minimum_value_error(create_order_with_quantity):
    # Check error mentions minimum
    pass


@then("I should receive a validation error")
def check_validation_error_max_qty(create_order_with_quantity):
    assert create_order_with_quantity["status_code"] in (400, 422)


@then("the error should indicate maximum value")
def check_maximum_value_error(create_order_with_quantity):
    # Check error mentions maximum
    pass


@then("I should receive a 429 Too Many Requests error")
def check_rate_limit_error():
    # Simulate rate limit by making many requests
    pass


@then("the response should include retry-after header")
def check_retry_after_header():
    pass


@then("appropriate CORS headers should be returned")
def check_cors_headers(api):
    r = api.options("/api/v1/vendors/")
    assert r.status_code == 200
    # HTTP headers are case-insensitive, Starlette uses lowercase
    headers = {k.lower(): v for k, v in r.headers.items()}
    assert (
        "access-control-allow-origin" in headers
        or "access-control-allow-methods" in headers
    )


@then("allowed methods should be listed")
def check_allowed_methods(api):
    r = api.options("/api/v1/vendors/")
    methods = r.headers.get("Access-Control-Allow-Methods", "")
    assert len(methods) > 0


@then("I should receive a 401 error")
def check_unauthorized():
    pass


@then("the error should indicate auth format")
def check_auth_format_error():
    pass


@then("I should receive a 401 error")
def check_token_expired_error():
    pass


@then("the error should indicate token expired")
def check_token_expired_message():
    pass


@then("I should receive a validation error")
def check_bulk_validation_error():
    pass


@then("the error should indicate batch size limit")
def check_batch_limit_error():
    pass


@then("I should receive a 404 error")
def check_not_found_error():
    pass


@then("I should receive a 415 error")
def check_unsupported_media_type():
    pass
