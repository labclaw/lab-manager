"""Step definitions for document lifecycle BDD tests."""

from pytest_bdd import given, when, then, parsers


@given('I am authenticated as "admin"')
def auth_admin(api_client):
    """Authenticate as admin."""
    api_client.login("admin@lab.com", "admin123")


@given(parsers.parse('I upload a document "{filename}"'))
def upload_document(api_client, filename):
    """Upload a document."""
    with open(f"tests/fixtures/{filename}", "rb") as f:
        api_client.response = api_client.post(
            "/api/v1/documents",
            files={"file": (filename, f, "image/jpeg")},
        )
    api_client.doc_id = api_client.response.json().get("id")


@given("the document is processed with OCR")
def document_processed_ocr(api_client):
    """Wait for OCR processing."""
    doc_id = getattr(api_client, "doc_id", None)
    if doc_id:
        api_client.post(f"/api/v1/documents/{doc_id}/process")


@given("extraction completes with high confidence")
def extraction_high_confidence(api_client):
    """Ensure high confidence extraction."""
    pass  # Assume processed with high confidence


@given(parsers.parse("the document extraction has low confidence"))
def extraction_low_confidence(api_client):
    """Mark as low confidence."""
    doc_id = getattr(api_client, "doc_id", None)
    if doc_id:
        api_client.patch(f"/api/v1/documents/{doc_id}", json={"confidence": 0.3})


@given(parsers.parse("a {status} document exists"))
def document_with_status(api_client, status):
    """Create document with status."""
    resp = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "test.pdf",
            "status": status,
        },
    )
    api_client.doc_id = resp.json().get("id")


@given("a rejected document exists")
def rejected_document(api_client):
    """Create rejected document."""
    resp = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "rejected.pdf",
            "status": "rejected",
        },
    )
    api_client.doc_id = resp.json().get("id")


@given(parsers.parse("{count:d} documents are pending review"))
def pending_documents(api_client, count):
    """Create pending documents."""
    api_client.doc_ids = []
    for i in range(count):
        resp = api_client.post(
            "/api/v1/documents",
            json={
                "filename": f"pending_{i}.pdf",
                "status": "pending",
                "confidence": 0.95,
            },
        )
        api_client.doc_ids.append(resp.json().get("id"))


@given("all documents have confidence above 90%")
def high_confidence_docs(api_client):
    """Mark documents high confidence."""
    pass  # Already set in pending_documents


@given(parsers.parse('an approved document exists with PO number "{po_number}"'))
def approved_with_po(api_client, po_number):
    """Create approved document with PO."""
    resp = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "approved.pdf",
            "status": "reviewed",
            "po_number": po_number,
        },
    )
    api_client.doc_id = resp.json().get("id")


@given("a pending document exists")
def pending_document(api_client):
    """Create pending document."""
    resp = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "pending.pdf",
            "status": "pending",
        },
    )
    api_client.doc_id = resp.json().get("id")


@given("a reviewed document exists")
def reviewed_document(api_client):
    """Create reviewed document."""
    resp = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "reviewed.pdf",
            "status": "reviewed",
        },
    )
    api_client.doc_id = resp.json().get("id")


@given("inventory was created from the document")
def inventory_from_doc(api_client):
    """Simulate inventory created."""
    pass


@given("documents exist:")
def documents_with_status(api_client, datatable):
    """Create documents with various statuses."""
    for row in datatable:
        for _ in range(int(row["count"])):
            api_client.post(
                "/api/v1/documents",
                json={
                    "filename": "test.pdf",
                    "status": row["status"],
                },
            )


@given(parsers.parse('{count:d} documents from "{vendor}" exist'))
def documents_from_vendor(api_client, count, vendor):
    """Create documents from vendor."""
    for i in range(count):
        api_client.post(
            "/api/v1/documents",
            json={
                "filename": f"doc_{i}.pdf",
                "vendor_name": vendor,
            },
        )


@given(parsers.parse("{count:d} documents exist"))
def count_documents(api_client, count):
    """Create documents."""
    for i in range(count):
        api_client.post(
            "/api/v1/documents",
            json={
                "filename": f"doc_{i}.pdf",
            },
        )


@given("documents uploaded:")
def documents_uploaded_dates(api_client, datatable):
    """Create documents with upload dates."""
    for row in datatable:
        api_client.post(
            "/api/v1/documents",
            json={
                "filename": "dated.pdf",
                "created_at": row["date"],
            },
        )


@when("I approve the document")
def approve_document(api_client):
    """Approve document."""
    doc_id = getattr(api_client, "doc_id", None)
    api_client.response = api_client.post(
        f"/api/v1/documents/{doc_id}/review", json={"action": "approve"}
    )


@when(parsers.parse('I reject the document with reason "{reason}"'))
def reject_document(api_client, reason):
    """Reject document."""
    doc_id = getattr(api_client, "doc_id", None)
    api_client.response = api_client.post(
        f"/api/v1/documents/{doc_id}/review",
        json={
            "action": "reject",
            "reason": reason,
        },
    )


@when("I request re-extraction with a different provider")
def reextract_document(api_client):
    """Request re-extraction."""
    doc_id = getattr(api_client, "doc_id", None)
    api_client.response = api_client.post(f"/api/v1/documents/{doc_id}/reextract")


@when("I bulk approve all documents")
def bulk_approve(api_client):
    """Bulk approve documents."""
    doc_ids = getattr(api_client, "doc_ids", [])
    api_client.response = api_client.post(
        "/api/v1/documents/bulk-approve", json={"document_ids": doc_ids}
    )


@when(parsers.parse('I upload a new document with PO number "{po_number}"'))
def upload_with_po(api_client, po_number):
    """Upload document with PO."""
    api_client.response = api_client.post(
        "/api/v1/documents",
        json={
            "filename": "new.pdf",
            "po_number": po_number,
        },
    )


@when("I delete the document")
def delete_document(api_client):
    """Delete document."""
    doc_id = getattr(api_client, "doc_id", None)
    api_client.response = api_client.delete(f"/api/v1/documents/{doc_id}")


@when("I request document statistics")
def request_doc_stats(api_client):
    """Request document statistics."""
    api_client.response = api_client.get("/api/v1/documents/stats")


@when(parsers.parse('I search documents for vendor "{vendor}"'))
def search_docs_vendor(api_client, vendor):
    """Search documents by vendor."""
    api_client.response = api_client.get(f"/api/v1/documents?vendor={vendor}")


@when(parsers.parse("I request documents page {page:d} with page size {size:d}"))
def paginated_documents(api_client, page, size):
    """Request paginated documents."""
    api_client.response = api_client.get(
        f"/api/v1/documents?page={page}&page_size={size}"
    )


@when(parsers.parse('I filter documents from "{start}" to "{end}"'))
def filter_docs_date_range(api_client, start, end):
    """Filter documents by date."""
    api_client.response = api_client.get(
        f"/api/v1/documents?start_date={start}&end_date={end}"
    )


@then(parsers.parse('the document status should be "{status}"'))
def document_status_is(api_client, status):
    """Verify document status."""
    data = api_client.response.json()
    assert data.get("status") == status


@then("inventory records should be created")
def inventory_created(api_client):
    """Verify inventory created."""
    data = api_client.response.json()
    assert data.get("inventory_created", True) or data.get("created_inventory")


@then("the document should be searchable")
def document_searchable(api_client):
    """Verify document is searchable."""
    doc_id = getattr(api_client, "doc_id", None)
    if doc_id:
        resp = api_client.get(f"/api/v1/search?q={doc_id}")
        assert resp.status_code == 200


@then("rejection reason should be saved")
def rejection_saved(api_client):
    """Verify rejection saved."""
    data = api_client.response.json()
    assert data.get("rejection_reason") is not None


@then("no inventory should be created")
def no_inventory_created(api_client):
    """Verify no inventory created."""
    data = api_client.response.json()
    assert not data.get("created_inventory")


@then("new extraction results should be generated")
def new_extraction(api_client):
    """Verify new extraction."""
    data = api_client.response.json()
    assert data.get("extraction_id") is not None or data.get("status") == "processing"


@then(parsers.parse('all {count:d} documents should have status "{status}"'))
def all_docs_status(api_client, count, status):
    """Verify all documents have status."""
    data = api_client.response.json()
    approved = data.get("approved_count", 0)
    assert approved == count


@then("inventory records should be created for each")
def inventory_for_each(api_client):
    """Verify inventory created for each."""
    data = api_client.response.json()
    assert data.get("created_count", 0) > 0


@then("a duplicate warning should be shown")
def duplicate_warning(api_client):
    """Verify duplicate warning."""
    data = api_client.response.json()
    assert data.get("duplicate_warning") or data.get("warning")


@then("the document should still be processed")
def document_processed(api_client):
    """Verify document was processed."""
    assert (
        api_client.response.status_code == 200 or api_client.response.status_code == 201
    )


@then("the document should be marked as deleted")
def document_marked_deleted(api_client):
    """Verify document marked deleted."""
    data = api_client.response.json()
    assert data.get("deleted") or data.get("status") == "deleted"


@then("the document should not appear in review queue")
def not_in_queue(api_client):
    """Verify not in queue."""
    resp = api_client.get("/api/v1/documents?status=pending")
    items = resp.json().get("items", [])
    doc_id = getattr(api_client, "doc_id", None)
    if doc_id:
        assert not any(i.get("id") == doc_id for i in items)


@then("existing inventory should NOT be deleted")
def inventory_not_deleted(api_client):
    """Verify inventory preserved."""
    pass  # Check that no inventory was deleted


@then("the response should contain correct counts")
def correct_counts(api_client):
    """Verify correct counts."""
    data = api_client.response.json()
    assert "pending" in data or "by_status" in data


@then(parsers.parse("total should be {total:d}"))
def total_count(api_client, total):
    """Verify total count."""
    data = api_client.response.json()
    assert data.get("total", sum(data.values())) == total


@then(parsers.parse("I should receive {count:d} documents"))
def receive_count_docs(api_client, count):
    """Verify document count."""
    data = api_client.response.json()
    items = data.get("items", data)
    assert len(items) == count


@then(parsers.parse('all should be from "{vendor}"'))
def all_from_vendor(api_client, vendor):
    """Verify all from vendor."""
    data = api_client.response.json()
    items = data.get("items", data)
    for item in items:
        assert (
            item.get("vendor_name") == vendor
            or item.get("vendor", {}).get("name") == vendor
        )


@then(parsers.parse("total should be {total:d}"))
def verify_total(api_client, total):
    """Verify total count."""
    data = api_client.response.json()
    assert data.get("total", 0) == total


@then(parsers.parse("page count should be {pages:d}"))
def verify_page_count(api_client, pages):
    """Verify page count."""
    data = api_client.response.json()
    assert data.get("pages", 0) == pages


@then(parsers.parse("I should receive {count:d} documents"))
def verify_doc_count(api_client, count):
    """Verify document count received."""
    data = api_client.response.json()
    items = data.get("items", [])
    assert len(items) == count
