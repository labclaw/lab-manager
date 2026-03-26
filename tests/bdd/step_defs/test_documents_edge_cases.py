"""Step definitions for document edge case BDD scenarios."""

import itertools

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/documents_edge_cases.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Get non-existent document returns 404")
def test_get_nonexistent():
    pass


@scenario(FEATURE, "Reject document with path traversal")
def test_path_traversal():
    pass


@scenario(FEATURE, "Reject document with invalid status")
def test_invalid_status():
    pass


@scenario(FEATURE, "Update document fields")
def test_update_document():
    pass


@scenario(FEATURE, "Delete document soft-deletes")
def test_soft_delete():
    pass


@scenario(FEATURE, "List documents by document_type")
def test_list_by_type():
    pass


@scenario(FEATURE, "Search documents by file name")
def test_search_by_filename():
    pass


@scenario(FEATURE, "Approve document without extracted data creates no order")
def test_approve_no_data():
    pass


@scenario(FEATURE, "Get document by id")
def test_get_document():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Given steps ---


@given(
    parsers.parse('a test document exists with status "{status}"'),
    target_fixture="doc",
)
def create_test_doc(api, status):
    seq = next(_seq)
    r = api.post(
        "/api/v1/documents",
        json={
            "file_name": f"test_doc_{seq}.jpg",
            "file_path": f"/uploads/test_doc_{seq}.jpg",
            "status": status,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@given(
    parsers.parse(
        'a test document exists with status "{status}" and no extracted data'
    ),
    target_fixture="doc",
)
def create_test_doc_no_data(api, status):
    seq = next(_seq)
    r = api.post(
        "/api/v1/documents",
        json={
            "file_name": f"no_data_doc_{seq}.jpg",
            "file_path": f"/uploads/no_data_doc_{seq}.jpg",
            "status": status,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@given(parsers.parse('{n:d} test documents with type "{doc_type}" exist'))
def create_docs_with_type(api, n, doc_type):
    for i in range(n):
        seq = next(_seq)
        r = api.post(
            "/api/v1/documents",
            json={
                "file_name": f"type_doc_{seq}.jpg",
                "file_path": f"/uploads/type_doc_{seq}.jpg",
                "status": "pending",
                "document_type": doc_type,
            },
        )
        assert r.status_code == 201, r.text


@given(
    parsers.parse('a test document "{fname}" exists'),
    target_fixture="doc",
)
def create_named_doc(api, fname):
    r = api.post(
        "/api/v1/documents",
        json={
            "file_name": fname,
            "file_path": f"/uploads/{fname}",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- When steps ---


@when(
    parsers.parse("I get document with id {did:d}"),
    target_fixture="doc_resp",
)
def get_doc_nonexistent(api, did):
    return api.get(f"/api/v1/documents/{did}")


@when(
    parsers.parse('I try to create a document with path "{path}"'),
    target_fixture="doc_resp",
)
def create_doc_path_traversal(api, path):
    return api.post(
        "/api/v1/documents",
        json={
            "file_name": "evil.jpg",
            "file_path": path,
        },
    )


@when(
    parsers.parse('I try to create a document with invalid status "{status}"'),
    target_fixture="doc_resp",
)
def create_doc_invalid_status(api, status):
    return api.post(
        "/api/v1/documents",
        json={
            "file_name": "invalid_status.jpg",
            "file_path": "/uploads/invalid_status.jpg",
            "status": status,
        },
    )


@when(
    parsers.parse('I update the document vendor_name to "{vendor_name}"'),
    target_fixture="doc_update_resp",
)
def update_doc_vendor(api, doc, vendor_name):
    r = api.patch(
        f"/api/v1/documents/{doc['id']}",
        json={"vendor_name": vendor_name},
    )
    assert r.status_code == 200, r.text
    return r.json()


@when("I delete the test document", target_fixture="doc_resp")
def delete_doc(api, doc):
    return api.delete(f"/api/v1/documents/{doc['id']}")


@when(
    parsers.parse('I list documents with type "{doc_type}"'),
    target_fixture="doc_list",
)
def list_docs_by_type(api, doc_type):
    r = api.get("/api/v1/documents", params={"document_type": doc_type})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I search documents with query "{query}"'),
    target_fixture="doc_list",
)
def search_docs(api, query):
    r = api.get("/api/v1/documents", params={"search": query})
    assert r.status_code == 200, r.text
    return r.json()


@when("I approve the document", target_fixture="doc_review_resp")
def approve_doc(api, doc):
    r = api.post(
        f"/api/v1/documents/{doc['id']}/review",
        json={"action": "approve", "reviewed_by": "Robert"},
    )
    assert r.status_code == 200, r.text
    return r.json()


@when("I get the test document by id", target_fixture="doc_detail")
def get_doc_by_id(api, doc):
    r = api.get(f"/api/v1/documents/{doc['id']}")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse("the doc response status should be {code:d}"))
def check_doc_response(doc_resp, code):
    assert doc_resp.status_code == code


@then(parsers.parse('the document should have vendor_name "{vendor_name}"'))
def check_doc_vendor(doc_update_resp, vendor_name):
    assert doc_update_resp["vendor_name"] == vendor_name


@then(parsers.parse("the doc delete response should be {code:d}"))
def check_doc_delete(doc_resp, code):
    assert doc_resp.status_code == code


@then(parsers.parse("I should see {n:d} documents in the doc list"))
def check_doc_list_count(doc_list, n):
    assert doc_list["total"] == n


@then(parsers.parse("I should see {n:d} document in the doc list"))
def check_doc_list_count_singular(doc_list, n):
    assert doc_list["total"] == n


@then(parsers.parse('the document status should be "{status}" after review'))
def check_doc_review_status(doc_review_resp, status):
    assert doc_review_resp["status"] == status


@then("no order should be created from this document")
def check_no_order_from_doc(api, doc):
    r = api.get("/api/v1/orders", params={"page_size": 200})
    assert r.status_code == 200, r.text
    orders = r.json()["items"]
    doc_orders = [o for o in orders if o.get("document_id") == doc["id"]]
    assert len(doc_orders) == 0


@then(parsers.parse('the doc detail status should be "{status}"'))
def check_doc_detail_status(doc_detail, status):
    assert doc_detail["status"] == status
