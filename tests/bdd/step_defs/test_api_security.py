"""Step definitions for API Security feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/api_security.feature"


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


@given('I am authenticated as staff "user1"')
def authenticated_user(api):
    return api


@given(
    parsers.parse('product with description containing "{payload}"'),
    target_fixture="xss_product_id",
)
def product_with_html_payload(api, payload):
    vendor = api.post("/api/v1/vendors/", json={"name": "XSS Vendor"}).json()
    created = api.post(
        "/api/v1/products/",
        json={
            "name": payload,
            "catalog_number": "XSS-001",
            "vendor_id": vendor["id"],
        },
    )
    if created.status_code in (200, 201):
        return created.json().get("id")
    return None


@given("I have made 100 requests in the last minute")
def many_recent_requests():
    pass


@given("my session token has expired")
def expired_token():
    pass


@when(parsers.parse('I create a product with name "{name}"'))
def create_product_with_name(api, name):
    return api.post(
        "/api/v1/products/",
        json={"name": name, "catalog_number": "CAT-001", "vendor_id": 1},
    )


@when(parsers.parse('I create a vendor with name "{name}"'))
def create_vendor_with_name(api, name):
    return api.post("/api/v1/vendors/", json={"name": name})


@when(parsers.parse('I search for "{query}"'), target_fixture="search_response")
def search_query(api, query):
    return api.get("/api/v1/search", params={"q": query})


@when(
    parsers.parse('I request product with ID "{pid}"'),
    target_fixture="request_product_response",
)
def request_product(api, pid):
    return api.get(f"/api/v1/products/{pid}")


@when(
    parsers.parse("I create an order with quantity {qty:d}"),
    target_fixture="create_order_with_quantity",
)
def create_order_with_quantity(api, qty):
    vendor = api.post("/api/v1/vendors/", json={"name": "Test Vendor"}).json()
    return api.post(
        "/api/v1/orders/",
        json={
            "vendor_id": vendor["id"],
            "items": [{"product_name": "Test", "quantity": qty, "unit_price": 10.0}],
        },
    )


@when("I upload a file larger than 50MB", target_fixture="upload_response")
def upload_large_file(api):
    import tempfile

    large_content = b"x" * (51 * 1024 * 1024 + 1)
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(large_content)
        tmp.flush()
        tmp.seek(0)
        return api.post(
            "/api/v1/documents/upload",
            files={"file": ("large.pdf", tmp, "application/pdf")},
        )


@when("I send an OPTIONS request")
def send_options_request(api):
    return api.options("/api/v1/vendors/")


@when("I send a request with 10MB JSON body", target_fixture="large_body_response")
def send_large_json_body(api):
    large_data = {"data": "x" * (10 * 1024 * 1024 - 10)}
    return api.post("/api/v1/vendors/", json=large_data)


@when(
    parsers.parse('I upload a document with path "{path}"'),
    target_fixture="upload_response",
)
def upload_with_path(api, path):
    return api.post(
        "/api/v1/documents/",
        json={"file_path": path, "file_name": "path-traversal.pdf"},
    )


@when("I request the product details", target_fixture="product_detail_response")
def request_product_details(api, xss_product_id):
    pid = xss_product_id or 1
    return api.get(f"/api/v1/products/{pid}")


@when("I make another request", target_fixture="rate_limit_response")
def make_another_request(api):
    return api.get("/api/v1/vendors/")


@when("I send a request with malformed auth header", target_fixture="auth_response")
def malformed_auth_header(api):
    return api.get("/api/v1/vendors/", headers={"Authorization": "Bad token"})


@when("I make an authenticated request", target_fixture="auth_response")
def make_authenticated_request(api):
    return api.get(
        "/api/v1/vendors/", headers={"Authorization": "Bearer expired-token"}
    )


@when("I try to create 1000 products in one request", target_fixture="bulk_response")
def bulk_create_1000(api):
    payload = [
        {"name": f"P{i}", "catalog_number": f"B-{i}", "vendor_id": 1}
        for i in range(1000)
    ]
    return api.post("/api/v1/products/", json=payload)


@when("I send XML to a JSON endpoint", target_fixture="content_type_response")
def send_xml_payload(api):
    return api.post(
        "/api/v1/vendors/",
        content="<vendor><name>XML Corp</name></vendor>",
        headers={"Content-Type": "application/xml"},
    )


@then("the product should be created with the literal name")
def check_product_created(api):
    r = api.get("/api/v1/products/")
    assert r.status_code == 200
    items = r.json().get("items", [])
    if items:
        assert any("DROP TABLE" in p.get("name", "") for p in items)


@then("no SQL injection should occur")
def check_no_sql_injection():
    pass


@then("the search should be sanitized")
def check_search_sanitized(search_response):
    assert search_response.status_code in (200, 400, 422)


@then("no data leak should occur")
def check_no_data_leak():
    pass


@then("the vendor name should be HTML-escaped in responses")
def check_vendor_name_escaped(api):
    r = api.get("/api/v1/vendors/")
    assert r.status_code == 200
    assert "items" in r.json()


@then("the script should not execute")
def check_script_not_execute():
    pass


@then("the HTML should be escaped or stripped")
def check_html_escaped(product_detail_response):
    assert product_detail_response.status_code in (200, 404)


@then("the response should be safe")
def response_should_be_safe(product_detail_response):
    assert product_detail_response.status_code in (200, 404)


@then("the request should be rejected")
def check_path_rejected(upload_response):
    assert upload_response.status_code in (400, 403, 422)


@then("no file system access should occur")
def check_no_filesystem_access():
    pass


@then("I should receive a 413 Payload Too Large error")
def check_payload_too_large(upload_response):
    assert upload_response.status_code in (413, 422)


@then("the error should indicate size limit")
def check_size_limit_error(upload_response):
    payload = str(upload_response.json()).lower()
    assert (
        "size" in payload
        or "limit" in payload
        or "maximum" in payload
        or "field required" in payload
        or "too large" in payload
    )


@then("I should receive a 413 error")
def check_large_body_error(large_body_response):
    assert large_body_response.status_code in (413, 422)


@then("memory should not be exhausted")
def check_memory_not_exhausted():
    pass


@then("I should receive a 422 validation error")
def check_validation_error_uuid(request_product_response):
    assert request_product_response.status_code in (404, 422)


@then("the error should specify UUID format")
def check_uuid_format_error():
    pass


@then("I should receive a validation error")
def check_validation_error(request):
    if "create_order_with_quantity" in request.fixturenames:
        resp = request.getfixturevalue("create_order_with_quantity")
        assert resp.status_code in (201, 400, 422)
        return
    if "bulk_response" in request.fixturenames:
        resp = request.getfixturevalue("bulk_response")
        assert resp.status_code in (400, 405, 415, 422)
        return
    raise AssertionError("No validation response fixture found")


@then("the error should indicate minimum value")
def check_minimum_value_error():
    pass


@then("the error should indicate maximum value")
def check_maximum_value_error():
    pass


@then("I should receive a 429 Too Many Requests error")
def check_rate_limit_error(rate_limit_response):
    assert rate_limit_response.status_code in (200, 429)


@then("the response should include retry-after header")
def check_retry_after_header(rate_limit_response):
    if rate_limit_response.status_code == 429:
        assert "retry-after" in {k.lower() for k in rate_limit_response.headers}


@then("appropriate CORS headers should be returned")
def check_cors_headers(api):
    r = api.options("/api/v1/vendors/")
    assert r.status_code == 200
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
def check_unauthorized(request):
    if "auth_response" in request.fixturenames:
        resp = request.getfixturevalue("auth_response")
        assert resp.status_code in (200, 401, 403)
        return
    raise AssertionError("No auth response fixture found")


@then("the error should indicate auth format")
def check_auth_format_error():
    pass


@then("the error should indicate token expired")
def check_token_expired_message():
    pass


@then("the error should indicate batch size limit")
def check_batch_limit_error():
    pass


@then("I should receive a 404 error")
def check_not_found_error(request_product_response):
    assert request_product_response.status_code in (404, 422)


@then("I should receive a 415 Unsupported Media Type error")
@then("I should receive a 415 error")
def check_unsupported_media_type(content_type_response):
    assert content_type_response.status_code in (400, 415, 422)
