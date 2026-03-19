"""Step definitions for document intake BDD scenarios."""

import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/document_intake.feature"


def _table_to_dicts(datatable: list[list]) -> list[dict]:
    """Convert pytest-bdd raw datatable (list of lists) to list of dicts."""
    headers = [str(h).strip() for h in datatable[0]]
    return [{headers[i]: str(cell).strip() for i, cell in enumerate(row)} for row in datatable[1:]]


# --- Scenarios ---


@scenario(FEATURE, "Create a new document record")
def test_create_document():
    pass


@scenario(FEATURE, "List documents with status filter")
def test_list_with_filter():
    pass


@scenario(FEATURE, "Approve document creates order")
def test_approve_creates_order():
    pass


@scenario(FEATURE, "Reject document with reason")
def test_reject_with_reason():
    pass


@scenario(FEATURE, "Document statistics")
def test_document_statistics():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    """Shared context dict for passing data between steps."""
    return {}


# --- Given steps ---


@given(
    parsers.parse("the following documents exist:"),
    target_fixture="doc_list",
)
def create_documents_from_table(api, datatable):
    rows = _table_to_dicts(datatable)
    docs = []
    for row in rows:
        r = api.post(
            "/api/documents/",
            json={
                "file_name": row["file_name"],
                "file_path": f"/uploads/{row['file_name']}",
                "status": row["status"],
                "vendor_name": row["vendor_name"],
            },
        )
        assert r.status_code == 201, r.text
        docs.append(r.json())
    return docs


@given(
    parsers.parse('a document with status "{status}" and extracted data:'),
    target_fixture="test_doc",
)
def create_doc_with_extracted_data(api, ctx, status, datatable):
    rows = _table_to_dicts(datatable)
    extracted = {}
    doc_type = None
    vendor_name = None
    for row in rows:
        key = row["field"].strip()
        value = row["value"].strip()
        if key == "document_type":
            doc_type = value
        elif key == "vendor_name":
            vendor_name = value
        else:
            extracted[key] = value
    # Also put vendor_name in extracted_data so _create_order_from_doc can find it
    if vendor_name:
        extracted["vendor_name"] = vendor_name

    r = api.post(
        "/api/documents/",
        json={
            "file_name": f"doc_{status}.jpg",
            "file_path": f"/uploads/doc_{status}.jpg",
            "status": status,
            "document_type": doc_type,
            "vendor_name": vendor_name,
            "extracted_data": extracted,
        },
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    ctx["extracted_data"] = extracted
    return doc


@given("the document has extracted items:", target_fixture="test_doc")
def add_extracted_items(api, test_doc, ctx, datatable):
    rows = _table_to_dicts(datatable)
    items = []
    for row in rows:
        items.append(
            {
                "catalog_number": row["catalog_number"],
                "description": row["description"],
                "quantity": int(row["quantity"]),
                "unit": row["unit"],
            }
        )
    extracted = ctx["extracted_data"]
    extracted["items"] = items
    # Patch the document with updated extracted_data
    r = api.patch(
        f"/api/documents/{test_doc['id']}",
        json={"extracted_data": extracted},
    )
    assert r.status_code == 200, r.text
    return r.json()


@given(
    parsers.parse('a document with status "{status}"'),
    target_fixture="test_doc",
)
def create_doc_simple(api, status):
    r = api.post(
        "/api/documents/",
        json={
            "file_name": f"doc_{status}_simple.jpg",
            "file_path": f"/uploads/doc_{status}_simple.jpg",
            "status": status,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


@given(
    parsers.parse('{count:d} documents with status "{status}"'),
    target_fixture="bulk_docs",
)
def create_bulk_documents(api, count, status):
    docs = []
    for i in range(count):
        r = api.post(
            "/api/documents/",
            json={
                "file_name": f"bulk_{status}_{i}.jpg",
                "file_path": f"/uploads/bulk_{status}_{i}.jpg",
                "status": status,
            },
        )
        assert r.status_code == 201, r.text
        docs.append(r.json())
    return docs


# --- When steps ---


@when(
    parsers.parse('I create a document "{file_name}" at path "{file_path}"'),
    target_fixture="create_response",
)
def create_document(api, file_name, file_path):
    r = api.post(
        "/api/documents/",
        json={
            "file_name": file_name,
            "file_path": file_path,
        },
    )
    return r


@when(
    parsers.parse('I list documents with status "{status}"'),
    target_fixture="list_response",
)
def list_documents_filtered(api, status):
    r = api.get("/api/documents/", params={"status": status})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I approve the document reviewed by "{reviewer}"'),
    target_fixture="review_response",
)
def approve_document(api, test_doc, reviewer):
    r = api.post(
        f"/api/documents/{test_doc['id']}/review",
        json={"action": "approve", "reviewed_by": reviewer},
    )
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I reject the document with reason "{reason}"'),
    target_fixture="review_response",
)
def reject_document(api, test_doc, reason):
    r = api.post(
        f"/api/documents/{test_doc['id']}/review",
        json={"action": "reject", "reviewed_by": "scientist", "review_notes": reason},
    )
    assert r.status_code == 200, r.text
    return r.json()


@when("I request document statistics", target_fixture="stats_response")
def request_stats(api):
    r = api.get("/api/documents/stats")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse('the document should be created with status "{status}"'))
def check_created_status(create_response, status):
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["status"] == status


@then(parsers.parse('the document should have file_name "{file_name}"'))
def check_file_name(create_response, file_name):
    assert create_response.json()["file_name"] == file_name


@then(parsers.parse("I should see {count:d} documents"))
def check_document_count(list_response, count):
    assert len(list_response["items"]) == count


@then(parsers.parse('all documents should have status "{status}"'))
def check_all_status(list_response, status):
    for doc in list_response["items"]:
        assert doc["status"] == status


@then(parsers.parse('the document status should be "{status}"'))
def check_doc_status(review_response, status):
    assert review_response["status"] == status


@then(parsers.parse('the document reviewed_by should be "{reviewer}"'))
def check_reviewed_by(review_response, reviewer):
    assert review_response["reviewed_by"] == reviewer


@then(parsers.parse('an order should be created with po_number "{po}"'))
def check_order_created(api, test_doc, po):
    # List orders and find one linked to this document
    r = api.get("/api/orders/", params={"search": po})
    assert r.status_code == 200, r.text
    orders = r.json()["items"]
    matching = [o for o in orders if o.get("po_number") == po]
    assert len(matching) == 1, f"Expected 1 order with PO {po}, found {len(matching)}"


@then(parsers.parse('the order should have {count:d} item with catalog "{catalog}"'))
def check_order_item(api, test_doc, count, catalog):
    # Find the order linked to this document
    r = api.get("/api/orders/", params={"page_size": 200})
    assert r.status_code == 200, r.text
    orders = r.json()["items"]
    doc_order = [o for o in orders if o.get("document_id") == test_doc["id"]]
    assert len(doc_order) == 1, f"Expected 1 order for doc {test_doc['id']}, found {len(doc_order)}"
    order = doc_order[0]

    # Fetch order items (separate endpoint)
    r = api.get(f"/api/orders/{order['id']}/items")
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    matching = [it for it in items if it.get("catalog_number") == catalog]
    assert len(matching) == count, f"Expected {count} items with catalog {catalog}, found {len(matching)}"


@then(parsers.parse('the document review_notes should contain "{text}"'))
def check_review_notes(review_response, text):
    notes = review_response.get("review_notes", "") or ""
    assert text in notes, f"Expected '{text}' in review_notes, got '{notes}'"


@then(parsers.parse("the total should be {total:d}"))
def check_total(stats_response, total):
    assert stats_response["total_documents"] == total


@then(parsers.parse("approved count should be {count:d}"))
def check_approved_count(stats_response, count):
    assert stats_response["by_status"].get("approved", 0) == count


@then(parsers.parse("needs_review count should be {count:d}"))
def check_needs_review_count(stats_response, count):
    assert stats_response["by_status"].get("needs_review", 0) == count
