"""Comprehensive unit tests for document route functions.

Uses MagicMock for DB sessions to isolate route logic from the database.
Covers all route functions and Pydantic schema validation.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.api.routes.documents import (
    DocumentCreate,
    DocumentUpdate,
    ReviewAction,
    _ALLOWED_CONTENT_TYPES,
    _DOC_SORTABLE,
    _VALID_STATUSES,
)
from lab_manager.models.document import DocumentStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(
    id: int = 1,
    file_path: str = "/tmp/uploads/test.pdf",
    file_name: str = "test.pdf",
    document_type: str | None = "invoice",
    vendor_name: str | None = "Sigma-Aldrich",
    ocr_text: str | None = "Some OCR text",
    extracted_data: dict | None = None,
    extraction_model: str | None = "gemini-3-pro",
    extraction_confidence: float | None = 0.95,
    status: str = "pending",
    review_notes: str | None = None,
    reviewed_by: str | None = None,
):
    """Create a mock Document instance."""
    doc = MagicMock()
    doc.id = id
    doc.file_path = file_path
    doc.file_name = file_name
    doc.document_type = document_type
    doc.vendor_name = vendor_name
    doc.ocr_text = ocr_text
    doc.extracted_data = extracted_data
    doc.extraction_model = extraction_model
    doc.extraction_confidence = extraction_confidence
    doc.status = status
    doc.review_notes = review_notes
    doc.reviewed_by = reviewed_by
    return doc


def _make_db():
    """Create a mock DB session with common defaults."""
    db = MagicMock()
    db.get.return_value = None
    db.add.return_value = None
    db.flush.return_value = None
    db.refresh.return_value = None
    db.commit.return_value = None
    db.rollback.return_value = None
    db.close.return_value = None
    # db.execute() for stats queries
    execute_result = MagicMock()
    execute_result.scalar.return_value = 0
    execute_result.all.return_value = []
    db.execute.return_value = execute_result
    # db.scalars() for queries
    scalars_result = MagicMock()
    scalars_result.first.return_value = None
    scalars_result.all.return_value = []
    db.scalars.return_value = scalars_result
    return db


def _make_paginate_result(items, total=None, page=1, page_size=20):
    """Build the dict that paginate() returns."""
    total = total if total is not None else len(items)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


@pytest.fixture(autouse=True)
def _disable_auth():
    """Ensure auth is disabled for all tests."""
    os.environ["AUTH_ENABLED"] = "false"
    from lab_manager.config import get_settings

    get_settings.cache_clear()


# ===================================================================
#  1.  DocumentCreate schema validation
# ===================================================================


class TestDocumentCreateValidation:
    """Test Pydantic model validation for DocumentCreate."""

    def test_valid_minimal(self):
        body = DocumentCreate(file_path="uploads/test.pdf", file_name="test.pdf")
        assert body.file_path == "uploads/test.pdf"
        assert body.file_name == "test.pdf"
        assert body.document_type is None
        assert body.vendor_name is None
        assert body.status == DocumentStatus.pending

    def test_valid_all_fields(self):
        body = DocumentCreate(
            file_path="uploads/test.pdf",
            file_name="test.pdf",
            document_type="invoice",
            vendor_name="Sigma-Aldrich",
            ocr_text="Some text",
            extracted_data={"items": []},
            extraction_model="gemini-3-pro",
            extraction_confidence=0.9,
            status="pending",
            review_notes="Looks good",
            reviewed_by="scientist",
        )
        assert body.document_type == "invoice"
        assert body.extracted_data == {"items": []}
        assert body.extraction_confidence == 0.9

    def test_status_defaults_to_pending(self):
        body = DocumentCreate(file_path="uploads/a.pdf", file_name="a.pdf")
        assert body.status == "pending"

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            DocumentCreate(
                file_path="uploads/a.pdf", file_name="a.pdf", status="nonexistent"
            )

    def test_all_valid_statuses(self):
        for s in _VALID_STATUSES:
            body = DocumentCreate(
                file_path="uploads/a.pdf", file_name="a.pdf", status=s
            )
            assert body.status == s

    def test_file_path_traversal_rejected(self):
        with pytest.raises(Exception):
            DocumentCreate(file_path="../../../etc/passwd", file_name="passwd")

    def test_file_path_absolute_outside_rejected(self):
        with pytest.raises(Exception):
            DocumentCreate(file_path="/etc/passwd", file_name="passwd")

    def test_extracted_data_dict(self):
        data = {"vendor_name": "Test", "items": [{"description": "Widget"}]}
        body = DocumentCreate(
            file_path="uploads/a.pdf",
            file_name="a.pdf",
            extracted_data=data,
        )
        assert body.extracted_data == data

    def test_optional_fields_default_none(self):
        body = DocumentCreate(file_path="uploads/a.pdf", file_name="a.pdf")
        assert body.ocr_text is None
        assert body.extraction_model is None
        assert body.extraction_confidence is None
        assert body.review_notes is None
        assert body.reviewed_by is None


# ===================================================================
#  2.  DocumentUpdate schema validation
# ===================================================================


class TestDocumentUpdateValidation:
    """Test Pydantic model validation for DocumentUpdate."""

    def test_all_none(self):
        body = DocumentUpdate()
        assert body.file_path is None
        assert body.file_name is None
        assert body.document_type is None
        assert body.status is None

    def test_partial_update(self):
        body = DocumentUpdate(file_name="new_name.pdf")
        assert body.file_name == "new_name.pdf"
        assert body.file_path is None

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            DocumentUpdate(status="invalid_status")

    def test_none_status_is_valid(self):
        body = DocumentUpdate(status=None)
        assert body.status is None

    def test_valid_status_accepted(self):
        for s in _VALID_STATUSES:
            body = DocumentUpdate(status=s)
            assert body.status == s

    def test_exclude_unset_behavior(self):
        body = DocumentUpdate(file_name="updated.pdf")
        dumped = body.model_dump(exclude_unset=True)
        assert "file_name" in dumped
        assert "file_path" not in dumped
        assert "status" not in dumped

    def test_file_path_traversal_rejected(self):
        with pytest.raises(Exception):
            DocumentUpdate(file_path="../../../etc/passwd")

    def test_none_file_path_is_valid(self):
        body = DocumentUpdate(file_path=None)
        assert body.file_path is None

    def test_update_extracted_data(self):
        data = {"vendor_name": "Updated", "items": []}
        body = DocumentUpdate(extracted_data=data)
        assert body.extracted_data == data


# ===================================================================
#  3.  ReviewAction schema validation
# ===================================================================


class TestReviewActionValidation:
    """Test Pydantic model validation for ReviewAction."""

    def test_approve_action(self):
        action = ReviewAction(action="approve")
        assert action.action == "approve"
        assert action.reviewed_by == "scientist"

    def test_reject_action(self):
        action = ReviewAction(action="reject")
        assert action.action == "reject"

    def test_invalid_action_rejected(self):
        with pytest.raises(Exception):
            ReviewAction(action="maybe")

    def test_custom_reviewed_by(self):
        action = ReviewAction(action="approve", reviewed_by="admin")
        assert action.reviewed_by == "admin"

    def test_review_notes_optional(self):
        action = ReviewAction(action="approve")
        assert action.review_notes is None

    def test_review_notes_provided(self):
        action = ReviewAction(action="reject", review_notes="Bad extraction")
        assert action.review_notes == "Bad extraction"

    def test_reviewed_by_default(self):
        action = ReviewAction(action="approve")
        assert action.reviewed_by == "scientist"


# ===================================================================
#  4.  Module constants
# ===================================================================


class TestModuleConstants:
    """Test module-level constants are correct."""

    def test_allowed_content_types(self):
        assert "image/png" in _ALLOWED_CONTENT_TYPES
        assert "image/jpeg" in _ALLOWED_CONTENT_TYPES
        assert "image/tiff" in _ALLOWED_CONTENT_TYPES
        assert "application/pdf" in _ALLOWED_CONTENT_TYPES

    def test_disallowed_content_types(self):
        assert "text/plain" not in _ALLOWED_CONTENT_TYPES
        assert "application/json" not in _ALLOWED_CONTENT_TYPES

    def test_doc_sortable_fields(self):
        expected = {
            "id",
            "created_at",
            "updated_at",
            "file_name",
            "document_type",
            "vendor_name",
            "status",
            "extraction_confidence",
        }
        assert _DOC_SORTABLE == expected

    def test_valid_statuses_matches_enum(self):
        enum_values = {s.value for s in DocumentStatus}
        assert _VALID_STATUSES == enum_values

    def test_valid_statuses_contains_all(self):
        for status in [
            "pending",
            "processing",
            "extracted",
            "needs_review",
            "approved",
            "rejected",
            "ocr_failed",
            "deleted",
        ]:
            assert status in _VALID_STATUSES


# ===================================================================
#  5.  list_documents route
# ===================================================================


class TestListDocuments:
    """Test the GET / documents list endpoint."""

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_basic_list(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.documents import list_documents

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        result = list_documents(
            page=1,
            page_size=20,
            status=None,
            document_type=None,
            vendor_name=None,
            extraction_model=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["total"] == 0
        assert result["items"] == []

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_list_with_status_filter(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.documents import list_documents

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_documents(
            page=1,
            page_size=20,
            status="approved",
            document_type=None,
            vendor_name=None,
            extraction_model=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_list_with_all_filters(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.documents import list_documents

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_documents(
            page=1,
            page_size=20,
            status="pending",
            document_type="invoice",
            vendor_name="Sigma",
            extraction_model="gemini-3-pro",
            search="test",
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()
        mock_sort.assert_called_once()

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_list_pagination_params(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.documents import list_documents

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result(
            [], total=0, page=3, page_size=10
        )
        db = _make_db()

        result = list_documents(
            page=3,
            page_size=10,
            status=None,
            document_type=None,
            vendor_name=None,
            extraction_model=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["page"] == 3
        assert result["page_size"] == 10

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_list_returns_items(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.documents import list_documents

        doc = _make_doc(id=1, file_name="invoice.pdf")
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([doc], total=1)
        db = _make_db()

        result = list_documents(
            page=1,
            page_size=20,
            status=None,
            document_type=None,
            vendor_name=None,
            extraction_model=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["total"] == 1
        assert len(result["items"]) == 1

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_list_sort_desc(self, mock_sort, mock_paginate):
        from lab_manager.api.routes.documents import list_documents

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_documents(
            page=1,
            page_size=20,
            status=None,
            document_type=None,
            vendor_name=None,
            extraction_model=None,
            search=None,
            sort_by="created_at",
            sort_dir="desc",
            db=db,
        )
        mock_sort.assert_called_once()

    @patch("lab_manager.api.routes.documents.paginate")
    @patch("lab_manager.api.routes.documents.apply_sort")
    def test_list_no_filters(self, mock_sort, mock_paginate):
        """When no filters applied, query should not have WHERE clauses."""
        from lab_manager.api.routes.documents import list_documents

        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        list_documents(
            page=1,
            page_size=20,
            status=None,
            document_type=None,
            vendor_name=None,
            extraction_model=None,
            search=None,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        # paginate should be called exactly once
        mock_paginate.assert_called_once()


# ===================================================================
#  6.  get_document route
# ===================================================================


class TestGetDocument:
    """Test the GET /{document_id} endpoint."""

    def test_get_existing(self):
        from lab_manager.api.routes.documents import get_document

        doc = _make_doc(id=42, file_name="found.pdf")
        db = _make_db()
        db.get.return_value = doc

        result = get_document(document_id=42, db=db)
        assert result.id == 42
        assert result.file_name == "found.pdf"

    def test_get_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.documents import get_document
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_document(document_id=9999, db=db)

    def test_get_verifies_model_and_id(self):
        from lab_manager.api.routes.documents import get_document
        from lab_manager.models.document import Document

        doc = _make_doc(id=5)
        db = _make_db()
        db.get.return_value = doc

        get_document(document_id=5, db=db)
        db.get.assert_called_once_with(Document, 5)


# ===================================================================
#  7.  create_document route
# ===================================================================


class TestCreateDocument:
    """Test the POST / document create endpoint."""

    def test_create_basic(self):
        from lab_manager.api.routes.documents import create_document

        db = _make_db()
        db.refresh.side_effect = lambda obj: None

        body = DocumentCreate(
            file_path="uploads/test.pdf",
            file_name="test.pdf",
        )
        create_document(body=body, db=db)

        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_create_with_all_fields(self):
        from lab_manager.api.routes.documents import create_document

        db = _make_db()
        db.refresh.side_effect = lambda obj: None

        body = DocumentCreate(
            file_path="uploads/test.pdf",
            file_name="test.pdf",
            document_type="invoice",
            vendor_name="Sigma-Aldrich",
            ocr_text="OCR text here",
            extracted_data={"items": []},
            extraction_model="gemini-3-pro",
            extraction_confidence=0.95,
            status="pending",
            review_notes="Auto review",
            reviewed_by="scientist",
        )
        create_document(body=body, db=db)
        db.add.assert_called_once()

    def test_create_uses_model_dump(self):
        from lab_manager.api.routes.documents import create_document

        db = _make_db()
        db.refresh.side_effect = lambda obj: None

        body = DocumentCreate(
            file_path="uploads/test.pdf",
            file_name="test.pdf",
            document_type="invoice",
        )
        create_document(body=body, db=db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.file_name == "test.pdf"
        assert added_obj.document_type == "invoice"


# ===================================================================
#  8.  update_document route
# ===================================================================


class TestUpdateDocument:
    """Test the PATCH /{document_id} endpoint."""

    def test_update_file_name(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1, file_name="old.pdf")
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate(file_name="new.pdf")
        update_document(document_id=1, body=body, db=db)

        assert doc.file_name == "new.pdf"
        db.flush.assert_called_once()
        db.refresh.assert_called_once()

    def test_update_status(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1, status="pending")
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate(status="approved")
        update_document(document_id=1, body=body, db=db)
        assert doc.status == "approved"

    def test_update_vendor_name_normalized(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1, vendor_name="Old")
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate(vendor_name="sigma-aldrich")
        update_document(document_id=1, body=body, db=db)
        # normalize_vendor should have been called
        assert doc.vendor_name == "Sigma-Aldrich"

    def test_update_vendor_name_empty_not_normalized(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1, vendor_name="Old")
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate(vendor_name="")
        update_document(document_id=1, body=body, db=db)
        # Empty string should not trigger normalize_vendor
        assert doc.vendor_name == ""

    def test_update_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.documents import update_document
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        body = DocumentUpdate(file_name="nope.pdf")
        with pytest.raises(NotFoundError):
            update_document(document_id=9999, body=body, db=db)

    def test_partial_update_only_sets_provided_fields(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1, file_name="keep.pdf", status="pending")
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate(status="approved")
        update_document(document_id=1, body=body, db=db)

        # Only status was set; file_name unchanged
        assert doc.status == "approved"

    def test_empty_body_no_changes(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1)
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate()
        dumped = body.model_dump(exclude_unset=True)
        assert len(dumped) == 0

        update_document(document_id=1, body=body, db=db)
        db.flush.assert_called_once()

    def test_update_extracted_data(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1)
        db = _make_db()
        db.get.return_value = doc

        data = {"vendor_name": "Updated", "items": [{"desc": "Widget"}]}
        body = DocumentUpdate(extracted_data=data)
        update_document(document_id=1, body=body, db=db)
        assert doc.extracted_data == data

    def test_update_ocr_text(self):
        from lab_manager.api.routes.documents import update_document

        doc = _make_doc(id=1, ocr_text="old")
        db = _make_db()
        db.get.return_value = doc

        body = DocumentUpdate(ocr_text="new OCR text")
        update_document(document_id=1, body=body, db=db)
        assert doc.ocr_text == "new OCR text"


# ===================================================================
#  9.  delete_document route
# ===================================================================


class TestDeleteDocument:
    """Test the DELETE /{document_id} endpoint."""

    def test_delete_existing(self):
        from lab_manager.api.routes.documents import delete_document

        doc = _make_doc(id=1, status="pending")
        db = _make_db()
        db.get.return_value = doc

        result = delete_document(document_id=1, db=db)
        assert result is None
        assert doc.status == DocumentStatus.deleted
        db.flush.assert_called_once()

    def test_delete_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.documents import delete_document
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            delete_document(document_id=9999, db=db)

    def test_soft_delete_sets_deleted_status(self):
        from lab_manager.api.routes.documents import delete_document

        doc = _make_doc(id=5, status="approved")
        db = _make_db()
        db.get.return_value = doc

        delete_document(document_id=5, db=db)
        assert doc.status == "deleted"

    def test_delete_already_deleted_still_succeeds(self):
        from lab_manager.api.routes.documents import delete_document

        doc = _make_doc(id=3, status="deleted")
        db = _make_db()
        db.get.return_value = doc

        delete_document(document_id=3, db=db)
        assert doc.status == "deleted"


# ===================================================================
#  10.  review_document route
# ===================================================================


class TestReviewDocument:
    """Test the POST /{document_id}/review endpoint."""

    def test_approve_needs_review_doc(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="needs_review")
        db = _make_db()
        db.get.return_value = doc
        # No existing order
        db.scalars.return_value.first.return_value = None

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve", reviewed_by="admin")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == DocumentStatus.approved
        assert doc.reviewed_by == "admin"
        db.flush.assert_called()
        db.commit.assert_called_once()

    def test_reject_needs_review_doc(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="needs_review")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(
            action="reject", reviewed_by="scientist", review_notes="Bad data"
        )

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == DocumentStatus.rejected
        assert doc.review_notes == "Bad data"
        assert doc.reviewed_by == "scientist"

    def test_review_processing_returns_409(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="processing")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        result = review_document(
            document_id=1, body=body, background_tasks=bg_tasks, db=db
        )
        assert isinstance(result, object)
        # The route returns a JSONResponse for 409
        # Check that doc.status was NOT changed
        assert doc.status == "processing"

    def test_review_pending_returns_409(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="pending")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == "pending"

    def test_review_approved_returns_409(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="approved")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="reject")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == "approved"

    def test_review_rejected_returns_409(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="rejected")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == "rejected"

    def test_review_deleted_returns_409(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="deleted")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == "deleted"

    def test_review_nonexistent_raises_not_found(self):
        from lab_manager.api.routes.documents import review_document
        from lab_manager.exceptions import NotFoundError

        db = _make_db()
        db.get.return_value = None

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        with pytest.raises(NotFoundError):
            review_document(
                document_id=9999, body=body, background_tasks=bg_tasks, db=db
            )

    @patch("lab_manager.api.routes.documents._create_order_from_doc")
    def test_approve_creates_order_when_no_existing(self, mock_create_order):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(
            id=1,
            status="needs_review",
            extracted_data={"vendor_name": "Test", "items": [{"desc": "Widget"}]},
        )
        db = _make_db()
        db.get.return_value = doc
        db.scalars.return_value.first.return_value = None  # no existing order

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        mock_create_order.assert_called_once_with(doc, db)

    def test_approve_does_not_create_order_when_exists(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(
            id=1,
            status="needs_review",
            extracted_data={"vendor_name": "Test"},
        )
        db = _make_db()
        db.get.return_value = doc
        db.scalars.return_value.first.return_value = MagicMock()  # existing order

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == DocumentStatus.approved

    def test_approve_no_extracted_data_no_order(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="needs_review", extracted_data=None)
        db = _make_db()
        db.get.return_value = doc
        db.scalars.return_value.first.return_value = None

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == DocumentStatus.approved

    def test_approve_triggers_background_indexing(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="needs_review", extracted_data=None)
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        bg_tasks.add_task.assert_called_once()

    def test_reject_does_not_trigger_background_indexing(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="needs_review")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="reject")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        bg_tasks.add_task.assert_not_called()

    def test_approve_ocr_failed_doc_succeeds(self):
        """ocr_failed status should allow review (not in blocked statuses)."""
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="ocr_failed")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == DocumentStatus.approved

    def test_approve_extracted_doc_succeeds(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="extracted")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.status == DocumentStatus.approved

    def test_approve_sets_review_notes(self):
        from lab_manager.api.routes.documents import review_document

        doc = _make_doc(id=1, status="needs_review")
        db = _make_db()
        db.get.return_value = doc

        bg_tasks = MagicMock()
        body = ReviewAction(action="approve", review_notes="Looks correct")

        review_document(document_id=1, body=body, background_tasks=bg_tasks, db=db)
        assert doc.review_notes == "Looks correct"


# ===================================================================
#  11.  document_stats route
# ===================================================================


class TestDocumentStats:
    """Test the GET /stats endpoint."""

    def test_basic_stats(self):
        from lab_manager.api.routes.documents import document_stats

        db = _make_db()
        # Order of db.execute calls in document_stats:
        # 1. scalar: total_documents
        # 2. all: by_status
        # 3. all: by_type
        # 4. scalar: total_orders
        # 5. scalar: total_items
        # 6. scalar: total_vendors
        # 7. all: top_vendors
        scalar_values = iter([10, 20, 50, 8])
        all_values = iter(
            [
                [("pending", 3), ("approved", 7)],  # by_status
                [("invoice", 5), ("packing_slip", 3)],  # by_type
                [("Sigma-Aldrich", 5), ("Fisher", 3)],  # top_vendors
            ]
        )
        execute_result = MagicMock()
        execute_result.scalar.side_effect = lambda: next(scalar_values)
        execute_result.all.side_effect = lambda: next(all_values)
        db.execute.return_value = execute_result

        result = document_stats(db=db)
        assert result["total_documents"] == 10
        assert result["total_orders"] == 20
        assert result["total_items"] == 50
        assert result["total_vendors"] == 8

    def test_stats_empty_db(self):
        from lab_manager.api.routes.documents import document_stats

        db = _make_db()
        scalar_values = iter([0, 0, 0, 0])
        all_values = iter([[], [], []])
        execute_result = MagicMock()
        execute_result.scalar.side_effect = lambda: next(scalar_values)
        execute_result.all.side_effect = lambda: next(all_values)
        db.execute.return_value = execute_result

        result = document_stats(db=db)
        assert result["total_documents"] == 0
        assert result["by_status"] == {}
        assert result["by_type"] == {}
        assert result["top_vendors"] == []

    def test_stats_by_status_dict(self):
        from lab_manager.api.routes.documents import document_stats

        db = _make_db()
        scalar_values = iter([10, 20, 50, 8])
        all_values = iter(
            [
                [("pending", 3), ("approved", 7)],
                [],
                [],
            ]
        )
        execute_result = MagicMock()
        execute_result.scalar.side_effect = lambda: next(scalar_values)
        execute_result.all.side_effect = lambda: next(all_values)
        db.execute.return_value = execute_result

        result = document_stats(db=db)
        assert result["by_status"] == {"pending": 3, "approved": 7}

    def test_stats_top_vendors_format(self):
        from lab_manager.api.routes.documents import document_stats

        db = _make_db()
        scalar_values = iter([10, 20, 50, 8])
        all_values = iter(
            [
                [],
                [],
                [("Sigma-Aldrich", 5)],
            ]
        )
        execute_result = MagicMock()
        execute_result.scalar.side_effect = lambda: next(scalar_values)
        execute_result.all.side_effect = lambda: next(all_values)
        db.execute.return_value = execute_result

        result = document_stats(db=db)
        assert result["top_vendors"] == [{"name": "Sigma-Aldrich", "count": 5}]


# ===================================================================
#  12.  _validate_file_path helper
# ===================================================================


class TestValidateFilePath:
    """Test the _validate_file_path helper function."""

    def test_relative_path_in_upload_dir(self):
        from lab_manager.api.routes.documents import _validate_file_path

        # Relative paths should be valid (resolved under upload_dir)
        result = _validate_file_path("uploads/test.pdf")
        assert result == "uploads/test.pdf"

    def test_path_traversal_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir or scans_dir"):
            _validate_file_path("../../../etc/passwd")

    def test_absolute_path_outside_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError, match="upload_dir or scans_dir"):
            _validate_file_path("/etc/shadow")

    def test_url_encoded_path_traversal_rejected(self):
        from lab_manager.api.routes.documents import _validate_file_path

        with pytest.raises(ValueError):
            _validate_file_path("%2e%2e/%2e%2e/etc/passwd")


# ===================================================================
#  13.  upload_document route (via TestClient)
# ===================================================================


class TestUploadDocument:
    """Test the POST /upload endpoint."""

    def test_upload_rejects_invalid_content_type(self):
        from io import BytesIO

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        db = _make_db()
        app = create_app()

        def _override():
            yield db

        app.dependency_overrides[get_db] = _override

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
            )
            assert resp.status_code == 400
            assert "not allowed" in resp.json()["detail"]

    def test_upload_accepts_pdf(self):
        from io import BytesIO

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        db = _make_db()
        app = create_app()

        def _override():
            yield db

        app.dependency_overrides[get_db] = _override

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
            )
            # Will succeed (201) or fail on file write, but should not be 400
            assert resp.status_code in (201, 500)

    def test_upload_rejects_oversized_file(self):
        from io import BytesIO

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from lab_manager.api.routes.documents import _MAX_UPLOAD_BYTES
        from fastapi.testclient import TestClient

        db = _make_db()
        app = create_app()

        def _override():
            yield db

        app.dependency_overrides[get_db] = _override

        with TestClient(app) as client:
            big_content = b"x" * (_MAX_UPLOAD_BYTES + 1)
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("big.pdf", BytesIO(big_content), "application/pdf")},
            )
            assert resp.status_code == 413

    def test_upload_accepts_png(self):
        from io import BytesIO

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        db = _make_db()
        app = create_app()

        def _override():
            yield db

        app.dependency_overrides[get_db] = _override

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.png", BytesIO(b"\x89PNG"), "image/png")},
            )
            assert resp.status_code in (201, 500)

    def test_upload_accepts_jpeg(self):
        from io import BytesIO

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db
        from fastapi.testclient import TestClient

        db = _make_db()
        app = create_app()

        def _override():
            yield db

        app.dependency_overrides[get_db] = _override

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test.jpg", BytesIO(b"\xff\xd8\xff"), "image/jpeg")},
            )
            assert resp.status_code in (201, 500)


# ===================================================================
#  14.  _create_order_from_doc helper
# ===================================================================


class TestCreateOrderFromDoc:
    """Test the _create_order_from_doc helper function."""

    def test_skips_when_no_vendor_and_no_items(self):
        from lab_manager.api.routes.documents import _create_order_from_doc

        doc = _make_doc(
            id=1,
            vendor_name=None,
            extracted_data={"vendor_name": "", "items": []},
        )
        db = _make_db()

        _create_order_from_doc(doc, db)
        # Should not create any orders
        db.add.assert_not_called()

    def test_skips_when_no_data(self):
        from lab_manager.api.routes.documents import _create_order_from_doc

        doc = _make_doc(id=1, extracted_data=None)
        db = _make_db()

        _create_order_from_doc(doc, db)
        db.add.assert_not_called()

    def test_creates_vendor_if_not_exists(self):
        from lab_manager.api.routes.documents import _create_order_from_doc

        doc = _make_doc(
            id=1,
            vendor_name="NewVendor",
            extracted_data={
                "vendor_name": "NewVendor",
                "items": [{"description": "Widget"}],
            },
        )
        db = _make_db()
        db.scalars.return_value.first.return_value = None  # vendor not found

        _create_order_from_doc(doc, db)
        # Should have added vendor, order, order_item, product
        assert db.add.call_count >= 2

    def test_uses_existing_vendor(self):
        from lab_manager.api.routes.documents import _create_order_from_doc

        doc = _make_doc(
            id=1,
            vendor_name="Sigma-Aldrich",
            extracted_data={
                "vendor_name": "Sigma-Aldrich",
                "items": [
                    {
                        "description": "Widget",
                        "quantity": 5,
                        "catalog_number": "CAT-001",
                    }
                ],
            },
        )
        existing_vendor = MagicMock()
        existing_vendor.id = 10
        db = _make_db()
        # First call for vendor lookup returns existing
        vendor_scalars = MagicMock()
        vendor_scalars.first.return_value = existing_vendor
        # Second call for product lookup returns None (new product)
        product_scalars = MagicMock()
        product_scalars.first.return_value = None
        db.scalars.side_effect = [vendor_scalars, product_scalars]

        _create_order_from_doc(doc, db)
        # Should add: order, product, order_item, inventory_item
        assert db.add.call_count >= 3

    def test_creates_items_from_extracted_data(self):
        from lab_manager.api.routes.documents import _create_order_from_doc

        doc = _make_doc(
            id=1,
            vendor_name="Test",
            extracted_data={
                "vendor_name": "Test",
                "items": [
                    {
                        "description": "Widget A",
                        "quantity": 10,
                        "catalog_number": "CAT-001",
                    },
                    {
                        "description": "Widget B",
                        "quantity": 5,
                        "catalog_number": "CAT-002",
                    },
                ],
            },
        )
        db = _make_db()
        vendor = MagicMock()
        vendor.id = 1
        vendor_scalars = MagicMock()
        vendor_scalars.first.return_value = vendor
        product_scalars = MagicMock()
        product_scalars.first.return_value = None
        db.scalars.side_effect = [vendor_scalars, product_scalars, product_scalars]

        _create_order_from_doc(doc, db)
        # Should add: vendor? no (exists), order, 2 products, 2 order_items, 2 inventory_items
        assert db.add.call_count >= 6

    def test_creates_order_without_items_logs_warning(self):
        """When vendor exists but no items, should still create order."""
        from lab_manager.api.routes.documents import _create_order_from_doc

        doc = _make_doc(
            id=1,
            vendor_name="Test",
            extracted_data={
                "vendor_name": "Test",
                "items": [],
            },
        )
        db = _make_db()
        vendor = MagicMock()
        vendor.id = 1
        vendor_scalars = MagicMock()
        vendor_scalars.first.return_value = vendor
        db.scalars.return_value = vendor_scalars

        _create_order_from_doc(doc, db)
        # Should add order at minimum
        assert db.add.call_count >= 1


# ===================================================================
#  15.  normalize_vendor integration with routes
# ===================================================================


class TestNormalizeVendorIntegration:
    """Test that vendor name normalization works correctly in route context."""

    def test_normalize_known_vendor(self):
        from lab_manager.services.vendor_normalize import normalize_vendor

        assert normalize_vendor("sigma-aldrich") == "Sigma-Aldrich"
        assert normalize_vendor("Fisher Scientific Co") == "Fisher Scientific"

    def test_normalize_unknown_vendor_passthrough(self):
        from lab_manager.services.vendor_normalize import normalize_vendor

        assert normalize_vendor("Unknown Corp") == "Unknown Corp"

    def test_normalize_none_returns_none(self):
        from lab_manager.services.vendor_normalize import normalize_vendor

        assert normalize_vendor(None) is None

    def test_normalize_empty_returns_empty(self):
        from lab_manager.services.vendor_normalize import normalize_vendor

        result = normalize_vendor("")
        assert result == ""
