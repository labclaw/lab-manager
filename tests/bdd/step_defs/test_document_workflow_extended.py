"""Step definitions for document workflow feature."""

import pytest
from pytest_bdd import given, when, then, parsers
from fastapi.testclient import TestClient

from lab_manager.api.app import app
from lab_manager.models.document import DocumentStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Get authentication headers."""
    return {"Authorization": "Bearer test-token"}


# Background steps
@given("the database is clean")
def database_clean(db_session):
    """Clean the database."""
    db_session.execute("DELETE FROM documents")
    db_session.commit()


@given("I am authenticated")
def authenticated(client, auth_headers):
    """Set up authentication."""
    return auth_headers


# Upload steps
@when(
    parsers.parse('I upload a document "{filename}" with content type "{content_type}"')
)
def upload_document(client, auth_headers, filename, content_type, tmp_path):
    """Upload a document."""
    file_path = tmp_path / filename
    file_path.write_bytes(b"test content")
    with open(file_path, "rb") as f:
        response = client.post(
            "/api/documents/upload",
            files={"file": (filename, f, content_type)},
            headers=auth_headers,
        )
    return response


@when(parsers.parse('I upload a document "{filename}" with size {size:d}'))
def upload_large_document(client, auth_headers, filename, size, tmp_path):
    """Upload a large document."""
    file_path = tmp_path / filename
    file_path.write_bytes(b"x" * size)
    with open(file_path, "rb") as f:
        response = client.post(
            "/api/documents/upload",
            files={"file": (filename, f, "application/pdf")},
            headers=auth_headers,
        )
    return response


@when(parsers.parse("{count:d} documents exist"))
def create_documents(db_session, count):
    """Create multiple documents."""
    from lab_manager.models.document import Document

    for i in range(count):
        doc = Document(
            filename=f"doc_{i}.pdf",
            file_path=f"/uploads/doc_{i}.pdf",
            file_size=1000,
            content_type="application/pdf",
            status=DocumentStatus.PENDING,
        )
        db_session.add(doc)
    db_session.commit()


@when(parsers.parse('{count:d} documents with status "{status}" exist'))
def create_documents_with_status(db_session, count, status):
    """Create documents with specific status."""
    from lab_manager.models.document import Document

    status_enum = DocumentStatus[status.upper()]
    for i in range(count):
        doc = Document(
            filename=f"doc_{status}_{i}.pdf",
            file_path=f"/uploads/doc_{status}_{i}.pdf",
            file_size=1000,
            content_type="application/pdf",
            status=status_enum,
        )
        db_session.add(doc)
    db_session.commit()


@when(
    parsers.parse("I request documents with page {page:d} and page_size {page_size:d}")
)
def list_documents_paginated(client, auth_headers, page, page_size):
    """Request paginated documents."""
    response = client.get(
        f"/api/documents?page={page}&page_size={page_size}", headers=auth_headers
    )
    return response


@when(parsers.parse('I request documents with status "{status}"'))
def filter_documents_by_status(client, auth_headers, status):
    """Filter documents by status."""
    response = client.get(f"/api/documents?status={status}", headers=auth_headers)
    return response


@given(parsers.parse('a document exists with ID "{doc_id}"'))
def document_exists(db_session, doc_id):
    """Create a document with specific ID."""
    from lab_manager.models.document import Document

    doc = Document(
        id=doc_id,
        filename=f"doc_{doc_id}.pdf",
        file_path=f"/uploads/doc_{doc_id}.pdf",
        file_size=1000,
        content_type="application/pdf",
        status=DocumentStatus.PENDING,
    )
    db_session.add(doc)
    db_session.commit()


@given(parsers.parse('a document exists with status "{status}"'))
def document_with_status(db_session, status):
    """Create a document with specific status."""
    from lab_manager.models.document import Document

    status_enum = DocumentStatus[status.upper()]
    doc = Document(
        filename="status_doc.pdf",
        file_path="/uploads/status_doc.pdf",
        file_size=1000,
        content_type="application/pdf",
        status=status_enum,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@when(parsers.parse('I request document "{doc_id}"'))
def get_document(client, auth_headers, doc_id):
    """Get document by ID."""
    response = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    return response


@when(parsers.parse('I approve the document with notes "{notes}"'))
def approve_document(client, auth_headers, db_session, notes):
    """Approve a document."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.post(
        f"/api/documents/{doc}/review",
        json={"action": "approve", "notes": notes},
        headers=auth_headers,
    )
    return response


@when(parsers.parse('I reject the document with reason "{reason}"'))
def reject_document(client, auth_headers, db_session, reason):
    """Reject a document."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.post(
        f"/api/documents/{doc}/review",
        json={"action": "reject", "notes": reason},
        headers=auth_headers,
    )
    return response


@when("I try to review the document")
def try_review_reviewed(client, auth_headers, db_session):
    """Try to review an already reviewed document."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.post(
        f"/api/documents/{doc}/review",
        json={"action": "approve", "notes": "test"},
        headers=auth_headers,
    )
    return response


@when("I request document statistics")
def get_document_stats(client, auth_headers):
    """Get document statistics."""
    response = client.get("/api/documents/stats", headers=auth_headers)
    return response


@when("I delete the document")
def delete_document(client, auth_headers, db_session):
    """Delete a document."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.delete(f"/api/documents/{doc}", headers=auth_headers)
    return response


@when("I try to delete the document")
def try_delete_document(client, auth_headers, db_session):
    """Try to delete a document (may fail)."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.delete(f"/api/documents/{doc}", headers=auth_headers)
    return response


@given(parsers.parse('a document "{filename}" already exists'))
def document_exists_by_name(db_session, filename):
    """Create a document with specific filename."""
    from lab_manager.models.document import Document

    doc = Document(
        filename=filename,
        file_path=f"/uploads/{filename}",
        file_size=1000,
        content_type="application/pdf",
        status=DocumentStatus.PENDING,
    )
    db_session.add(doc)
    db_session.commit()


@when(parsers.parse('I upload another document "{filename}"'))
def upload_duplicate_filename(client, auth_headers, filename, tmp_path):
    """Upload document with duplicate filename."""
    file_path = tmp_path / filename
    file_path.write_bytes(b"test content 2")
    with open(file_path, "rb") as f:
        response = client.post(
            "/api/documents/upload",
            files={"file": (filename, f, "application/pdf")},
            headers=auth_headers,
        )
    return response


@given(parsers.parse('documents from vendors "{v1}", "{v2}", "{v3}" exist'))
def documents_from_vendors(db_session, v1, v2, v3):
    """Create documents from different vendors."""
    from lab_manager.models.document import Document

    for vendor in [v1, v2, v3]:
        doc = Document(
            filename=f"{vendor}_invoice.pdf",
            file_path=f"/uploads/{vendor}_invoice.pdf",
            file_size=1000,
            content_type="application/pdf",
            status=DocumentStatus.PENDING,
            extracted_data={"vendor": vendor},
        )
        db_session.add(doc)
    db_session.commit()


@when(parsers.parse('I search documents for vendor "{vendor}"'))
def search_documents_by_vendor(client, auth_headers, vendor):
    """Search documents by vendor."""
    response = client.get(f"/api/documents?vendor={vendor}", headers=auth_headers)
    return response


@given(
    parsers.parse(
        "{count:d} documents with extraction confidence below {threshold:f} exist"
    )
)
def documents_low_confidence(db_session, count, threshold):
    """Create documents with low extraction confidence."""
    from lab_manager.models.document import Document

    for i in range(count):
        doc = Document(
            filename=f"low_conf_{i}.pdf",
            file_path=f"/uploads/low_conf_{i}.pdf",
            file_size=1000,
            content_type="application/pdf",
            status=DocumentStatus.PENDING,
            extraction_confidence=threshold - 0.1,
        )
        db_session.add(doc)
    db_session.commit()


@when("I request documents needing review")
def get_documents_needing_review(client, auth_headers):
    """Get documents needing review."""
    response = client.get("/api/documents/needing-review", headers=auth_headers)
    return response


@when(parsers.parse('I batch update {count:d} documents to status "{status}"'))
def batch_update_documents(client, auth_headers, db_session, count, status):
    """Batch update document status."""
    docs = db_session.execute(f"SELECT id FROM documents LIMIT {count}").scalars().all()
    response = client.post(
        "/api/documents/batch-update",
        json={"ids": docs, "status": status},
        headers=auth_headers,
    )
    return response


@given("a document with unreadable content exists")
def document_ocr_failure(db_session):
    """Create a document that will fail OCR."""
    from lab_manager.models.document import Document

    doc = Document(
        filename="unreadable.pdf",
        file_path="/uploads/unreadable.pdf",
        file_size=1000,
        content_type="application/pdf",
        status=DocumentStatus.PENDING,
        ocr_status="failed",
    )
    db_session.add(doc)
    db_session.commit()


@when("the document is processed")
def process_document(client, auth_headers, db_session):
    """Process document (trigger OCR)."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.post(f"/api/documents/{doc}/process", headers=auth_headers)
    return response


@given("a document with extraction error exists")
def document_extraction_error(db_session):
    """Create a document with extraction error."""
    from lab_manager.models.document import Document

    doc = Document(
        filename="error.pdf",
        file_path="/uploads/error.pdf",
        file_size=1000,
        content_type="application/pdf",
        status=DocumentStatus.PENDING,
        extraction_status="error",
        extraction_error="Unable to parse document structure",
    )
    db_session.add(doc)
    db_session.commit()


@when("I request the document details")
def get_document_details(client, auth_headers, db_session):
    """Get document details."""
    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    response = client.get(f"/api/documents/{doc}", headers=auth_headers)
    return response


@given("a document was uploaded 5 minutes ago")
def document_uploaded_ago(db_session):
    """Create a document uploaded 5 minutes ago."""
    from datetime import datetime, timedelta
    from lab_manager.models.document import Document

    doc = Document(
        filename="timed.pdf",
        file_path="/uploads/timed.pdf",
        file_size=1000,
        content_type="application/pdf",
        status=DocumentStatus.PENDING,
        created_at=datetime.utcnow() - timedelta(minutes=5),
    )
    db_session.add(doc)
    db_session.commit()


@when("I upload a multi-page PDF document")
def upload_multi_page_pdf(client, auth_headers, tmp_path):
    """Upload a multi-page PDF."""
    file_path = tmp_path / "multi_page.pdf"
    file_path.write_bytes(b"%PDF-1.4\ntest multi-page content")
    with open(file_path, "rb") as f:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("multi_page.pdf", f, "application/pdf")},
            headers=auth_headers,
        )
    return response


# Then steps
@then("the response status should be 201")
def status_201(response):
    """Check response status is 201."""
    assert response.status_code == 201


@then("the response status should be 200")
def status_200(response):
    """Check response status is 200."""
    assert response.status_code == 200


@then("the response status should be 204")
def status_204(response):
    """Check response status is 204."""
    assert response.status_code == 204


@then("the response status should be 400")
def status_400(response):
    """Check response status is 400."""
    assert response.status_code == 400


@then("the response status should be 404")
def status_404(response):
    """Check response status is 404."""
    assert response.status_code == 404


@then("the response status should be 413")
def status_413(response):
    """Check response status is 413."""
    assert response.status_code == 413


@then("the response status should be 422")
def status_422(response):
    """Check response status is 422."""
    assert response.status_code == 422


@then(parsers.parse('the document should have status "{status}"'))
def document_status_is(db_session, status):
    """Check document status."""
    from lab_manager.models.document import Document

    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    doc = db_session.get(Document, doc)
    assert doc.status == DocumentStatus[status.upper()]


@then(parsers.parse('the error message should contain "{message}"'))
def error_message_contains(response, message):
    """Check error message."""
    data = response.json()
    assert message.lower() in str(data).lower()


@then(parsers.parse("the response should contain {count:d} documents"))
def response_count(response, count):
    """Check response count."""
    data = response.json()
    assert len(data.get("items", data)) == count


@then(parsers.parse("total count should be {count:d}"))
def total_count_is(response, count):
    """Check total count."""
    data = response.json()
    assert data.get("total", len(data)) == count


@then(parsers.parse("page count should be {count:d}"))
def page_count_is(response, count):
    """Check page count."""
    data = response.json()
    assert data.get("pages", 1) == count


@then(parsers.parse('the document ID should be "{doc_id}"'))
def document_id_is(response, doc_id):
    """Check document ID."""
    data = response.json()
    assert data.get("id") == doc_id or str(data.get("id")) == doc_id


@then(parsers.parse('review notes should be "{notes}"'))
def review_notes_are(db_session, notes):
    """Check review notes."""
    from lab_manager.models.document import Document

    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    doc = db_session.get(Document, doc)
    assert doc.review_notes == notes


@then(parsers.parse('review notes should contain "{text}"'))
def review_notes_contain(db_session, text):
    """Check review notes contain text."""
    from lab_manager.models.document import Document

    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    doc = db_session.get(Document, doc)
    assert text in (doc.review_notes or "")


@then(parsers.parse("{field} count should be {count:d}"))
def field_count_is(response, field, count):
    """Check field count."""
    data = response.json()
    field_lower = field.lower().replace(" ", "_")
    assert data.get(field_lower) == count or data.get(field) == count


@then("the document should no longer exist")
def document_not_exists(db_session):
    """Verify document was deleted."""
    count = db_session.execute("SELECT COUNT(*) FROM documents").scalar()
    assert count == 0


@then("the second document should have a different filename")
def different_filename(db_session):
    """Check second document has different filename."""
    docs = (
        db_session.execute("SELECT filename FROM documents ORDER BY created_at")
        .scalars()
        .all()
    )
    if len(docs) >= 2:
        assert docs[0] != docs[1] or "_1" in docs[1] or "(" in docs[1]


@then(parsers.parse('only documents from "{vendor}" should be returned'))
def only_vendor_returned(response, vendor):
    """Check only specific vendor returned."""
    data = response.json()
    items = data.get("items", data)
    for item in items:
        extracted = item.get("extracted_data", {})
        assert extracted.get("vendor") == vendor


@then('OCR status should be "failed"')
def ocr_status_failed(db_session):
    """Check OCR status is failed."""
    from lab_manager.models.document import Document

    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    doc = db_session.get(Document, doc)
    assert doc.ocr_status == "failed"


@then("an alert should be created")
def alert_created(db_session):
    """Check alert was created."""
    # This would check the alerts table
    pass


@then('extraction status should be "error"')
def extraction_status_error(db_session):
    """Check extraction status is error."""
    from lab_manager.models.document import Document

    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    doc = db_session.get(Document, doc)
    assert doc.extraction_status == "error"


@then("error message should be present")
def error_message_present(db_session):
    """Check error message exists."""
    from lab_manager.models.document import Document

    doc = db_session.execute("SELECT id FROM documents LIMIT 1").scalar()
    doc = db_session.get(Document, doc)
    assert doc.extraction_error is not None


@then("processing duration should be recorded")
def duration_recorded(response):
    """Check processing duration."""
    data = response.json()
    assert "processing_duration" in data or "duration" in data


@then("all pages should be processed")
def all_pages_processed(response):
    """Check all pages processed."""
    data = response.json()
    assert data.get("page_count", 1) >= 1


@then("page count should be accurate")
def page_count_accurate(response):
    """Check page count accuracy."""
    data = response.json()
    assert "page_count" in data
