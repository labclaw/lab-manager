"""Tests for iterative refinement of low-confidence extractions."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from lab_manager.config import get_settings
from lab_manager.intake.extractor import (
    MAX_REFINEMENT_ROUNDS,
    REFINEMENT_CONFIDENCE_THRESHOLD,
    extract_with_feedback,
)
from lab_manager.intake.schemas import ExtractedDocument


@pytest.fixture(autouse=True)
def _refinement_test_settings(monkeypatch):
    """Force tests to run with auth disabled."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("ADMIN_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password-not-for-production")
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite://"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestRefinementConstants:
    def test_threshold_is_reasonable(self):
        assert 0.0 < REFINEMENT_CONFIDENCE_THRESHOLD < 1.0

    def test_max_rounds_bounded(self):
        assert 1 <= MAX_REFINEMENT_ROUNDS <= 5


class TestExtractWithFeedback:
    def test_returns_none_on_no_api_key(self, monkeypatch):
        monkeypatch.setenv("EXTRACTION_MODEL", "gemini-3-pro-preview")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("EXTRACTION_API_KEY", "")
        get_settings.cache_clear()

        previous = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.3,
        )
        result = extract_with_feedback(
            "some ocr text",
            previous,
            "Low confidence. Re-examine vendor name.",
        )
        assert result is None

    def test_returns_result_on_success(self):
        previous = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.3,
        )
        improved = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            confidence=0.9,
        )

        with (
            patch(
                "lab_manager.intake.extractor._is_nvidia_model",
                return_value=True,
            ),
            patch(
                "lab_manager.intake.extractor._extract_nvidia_with_prompt",
                return_value=improved,
            ),
        ):
            result = extract_with_feedback(
                "Sigma-Aldrich packing list",
                previous,
                "Low confidence. Re-examine vendor name.",
            )

        assert result is not None
        assert result.vendor_name == "Sigma-Aldrich"
        assert result.confidence == 0.9

    def test_returns_none_on_exception(self):
        previous = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.3,
        )

        with (
            patch(
                "lab_manager.intake.extractor._is_nvidia_model",
                return_value=True,
            ),
            patch(
                "lab_manager.intake.extractor._extract_nvidia_with_prompt",
                side_effect=RuntimeError("API down"),
            ),
        ):
            result = extract_with_feedback(
                "some text",
                previous,
                "Issues found",
            )

        assert result is None


class TestPipelineRefinement:
    """Test the refinement loop integrated in process_document."""

    def test_refinement_triggered_on_low_confidence(self, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "low_conf.png"
        img.write_bytes(b"fake image")

        low_conf = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.4,
        )
        improved = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            confidence=0.85,
        )

        with (
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="Sigma-Aldrich packing list PO-123",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=low_conf,
            ),
            patch(
                "lab_manager.intake.extractor.extract_with_feedback",
                return_value=improved,
            ) as mock_refine,
        ):
            doc = process_document(img, db_session)

        # Refinement should have been called
        mock_refine.assert_called_once()
        assert doc.extraction_confidence == 0.85
        assert doc.vendor_name == "Sigma-Aldrich"
        assert "Refinement" in (doc.review_notes or "")

    def test_no_refinement_on_high_confidence(self, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "high_conf.png"
        img.write_bytes(b"fake image")

        good_extraction = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            confidence=0.95,
        )

        with (
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="Sigma-Aldrich packing list",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=good_extraction,
            ),
            patch(
                "lab_manager.intake.extractor.extract_with_feedback",
            ) as mock_refine,
        ):
            doc = process_document(img, db_session)

        # No refinement needed
        mock_refine.assert_not_called()
        assert doc.extraction_confidence == 0.95

    def test_refinement_stops_on_no_improvement(self, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "no_improve.png"
        img.write_bytes(b"fake image")

        low_conf = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.4,
        )
        still_low = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.35,
        )

        with (
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="some text",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=low_conf,
            ),
            patch(
                "lab_manager.intake.extractor.extract_with_feedback",
                return_value=still_low,
            ) as mock_refine,
        ):
            doc = process_document(img, db_session)

        # Only 1 refinement attempt (stopped because no improvement)
        assert mock_refine.call_count == 1
        assert doc.extraction_confidence == 0.4  # kept original
        assert "no improvement" in (doc.review_notes or "")

    def test_refinement_stops_on_failure(self, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "refine_fail.png"
        img.write_bytes(b"fake image")

        low_conf = ExtractedDocument(
            vendor_name="Unknown",
            document_type="other",
            confidence=0.4,
        )

        with (
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="some text",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=low_conf,
            ),
            patch(
                "lab_manager.intake.extractor.extract_with_feedback",
                return_value=None,
            ) as mock_refine,
        ):
            doc = process_document(img, db_session)

        assert mock_refine.call_count == 1
        assert doc.extraction_confidence == 0.4
        assert "failed" in (doc.review_notes or "")

    def test_refinement_triggered_on_validation_issues(self, db_session, tmp_path):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "validation_issues.png"
        img.write_bytes(b"fake image")

        bad_extraction = ExtractedDocument(
            vendor_name="123 Main Street Suite 400",
            document_type="packing_list",
            confidence=0.85,
            items=[],
        )
        fixed_extraction = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            confidence=0.92,
            items=[],
        )

        with (
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="Sigma-Aldrich 123 Main Street",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=bad_extraction,
            ),
            patch(
                "lab_manager.intake.extractor.extract_with_feedback",
                return_value=fixed_extraction,
            ) as mock_refine,
        ):
            doc = process_document(img, db_session)

        # Refinement triggered because vendor_name looks like an address
        mock_refine.assert_called_once()
        feedback_arg = mock_refine.call_args[0][2]
        assert "looks_like_address" in feedback_arg
