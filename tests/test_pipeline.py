"""Tests for document intake pipeline."""

from unittest.mock import patch

from lab_manager.intake.pipeline import process_document
from lab_manager.models.document import DocumentStatus


def test_process_document_records_failure_on_ocr_error(db_session, tmp_path):
    """OCR failure should create document with error status, not raise."""
    img = tmp_path / "test_doc.png"
    img.write_bytes(b"fake image data")

    with patch(
        "lab_manager.intake.pipeline.extract_text_from_image",
        side_effect=RuntimeError("OCR failed"),
    ):
        doc = process_document(img, db_session)

    assert doc is not None
    assert doc.status == DocumentStatus.needs_review
    assert "OCR failed" in (doc.review_notes or "")


def test_process_document_records_failure_on_extraction_error(db_session, tmp_path):
    """Extraction failure should create document with error status."""
    img = tmp_path / "test_doc2.png"
    img.write_bytes(b"fake image data")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value="some text",
        ),
        patch(
            "lab_manager.intake.pipeline.extract_from_text",
            side_effect=ValueError("Bad extraction"),
        ),
    ):
        doc = process_document(img, db_session)

    assert doc is not None
    assert doc.status == DocumentStatus.needs_review
    assert "Extraction failed" in (doc.review_notes or "")


def test_process_document_dedup_uses_content_hash(db_session, tmp_path):
    """Same filename with different content from different directories should both be processed."""
    dir1 = tmp_path / "batch1"
    dir2 = tmp_path / "batch2"
    dir1.mkdir()
    dir2.mkdir()

    img1 = dir1 / "doc.png"
    img2 = dir2 / "doc.png"
    img1.write_bytes(b"image content 1")
    img2.write_bytes(b"image content 2")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value="text",
        ),
        patch("lab_manager.intake.pipeline.extract_from_text") as mock_extract,
    ):
        from lab_manager.intake.schemas import ExtractedDocument

        mock_extract.return_value = ExtractedDocument(
            vendor_name="Test", document_type="other", items=[]
        )
        doc1 = process_document(img1, db_session)
        doc2 = process_document(img2, db_session)

    # Both should be processed (different source content)
    assert doc1.id != doc2.id


def test_process_document_true_duplicate_returns_existing(db_session, tmp_path):
    """Same file content submitted twice should return existing document."""
    dir1 = tmp_path / "batch1"
    dir2 = tmp_path / "batch2"
    dir1.mkdir()
    dir2.mkdir()

    img1 = dir1 / "doc.png"
    img2 = dir2 / "doc.png"
    # Same content = same hash
    img1.write_bytes(b"identical content")
    img2.write_bytes(b"identical content")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value="text",
        ),
        patch("lab_manager.intake.pipeline.extract_from_text") as mock_extract,
    ):
        from lab_manager.intake.schemas import ExtractedDocument

        mock_extract.return_value = ExtractedDocument(
            vendor_name="Test", document_type="other", items=[]
        )
        doc1 = process_document(img1, db_session)
        doc2 = process_document(img2, db_session)

    # True duplicates should return the same document
    assert doc1.id == doc2.id


def test_process_document_success(db_session, tmp_path):
    """Happy path: OCR + extraction succeed, document is created."""
    img = tmp_path / "good_doc.png"
    img.write_bytes(b"good image data")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value="Sigma-Aldrich PO-123",
        ),
        patch("lab_manager.intake.pipeline.extract_from_text") as mock_extract,
    ):
        from lab_manager.intake.schemas import ExtractedDocument

        mock_extract.return_value = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            po_number="PO-123",
            items=[],
            confidence=0.95,
        )
        doc = process_document(img, db_session)

    assert doc.status == DocumentStatus.needs_review
    assert doc.vendor_name == "Sigma-Aldrich"
    assert doc.document_type == "packing_list"
    assert doc.ocr_text == "Sigma-Aldrich PO-123"
    assert doc.extraction_confidence == 0.95


def test_process_document_empty_ocr_shortcircuits(db_session, tmp_path):
    """Empty OCR text should mark document as ocr_failed without calling VLM."""
    img = tmp_path / "blank_page.png"
    img.write_bytes(b"fake blank image")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value="",
        ) as mock_ocr,
        patch(
            "lab_manager.intake.pipeline.extract_from_text",
        ) as mock_extract,
    ):
        doc = process_document(img, db_session)

    mock_ocr.assert_called_once()
    mock_extract.assert_not_called()
    assert doc.status == DocumentStatus.ocr_failed
    assert "empty" in (doc.review_notes or "").lower()


def test_process_document_none_ocr_shortcircuits(db_session, tmp_path):
    """None OCR text should mark document as ocr_failed."""
    img = tmp_path / "bad_scan.png"
    img.write_bytes(b"fake bad scan")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value=None,
        ) as mock_ocr,
        patch(
            "lab_manager.intake.pipeline.extract_from_text",
        ) as mock_extract,
    ):
        doc = process_document(img, db_session)

    mock_ocr.assert_called_once()
    mock_extract.assert_not_called()
    assert doc.status == DocumentStatus.ocr_failed


def test_process_document_whitespace_ocr_shortcircuits(db_session, tmp_path):
    """Whitespace-only OCR should mark document as ocr_failed."""
    img = tmp_path / "white_page.png"
    img.write_bytes(b"fake white page")

    with (
        patch(
            "lab_manager.intake.pipeline.extract_text_from_image",
            return_value="   \n\t  ",
        ) as mock_ocr,
        patch(
            "lab_manager.intake.pipeline.extract_from_text",
        ) as mock_extract,
    ):
        doc = process_document(img, db_session)

    mock_ocr.assert_called_once()
    mock_extract.assert_not_called()
    assert doc.status == DocumentStatus.ocr_failed
