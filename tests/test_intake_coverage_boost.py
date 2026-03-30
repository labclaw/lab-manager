"""Targeted tests to boost coverage for intake/ocr, routing, extractor, providers, pipeline.

Covers specific uncovered lines identified by coverage analysis.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from lab_manager.intake.schemas import ExtractedDocument

SAMPLE_EXTRACTED = ExtractedDocument(
    vendor_name="Sigma-Aldrich",
    document_type="packing_list",
    po_number="PO-999",
    items=[{"catalog_number": "A1234", "quantity": 2}],
    confidence=0.9,
)

SAMPLE_OCR = "Sigma-Aldrich PO-999 Catalog A1234 Qty 2"


def _make_settings(**overrides):
    """Create a mock settings object with sensible defaults."""
    defaults = {
        "extraction_model": "gemini-2.5-flash",
        "extraction_api_key": "",
        "gemini_api_key": "",
        "google_api_key": "",
        "nvidia_build_api_key": "",
        "ocr_model": "",
        "ocr_tier": "auto",
        "ocr_local_model": "glm_ocr_09b",
        "ocr_local_url": "",
        "upload_dir": "/tmp/lab-manager-test-uploads",
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _make_mock_httpx(post_return=None, post_side_effect=None):
    mock = MagicMock()
    mock.HTTPStatusError = httpx.HTTPStatusError
    if post_side_effect is not None:
        mock.post.side_effect = post_side_effect
    elif post_return is not None:
        mock.post.return_value = post_return
    return mock


# ============================================================
# ocr.py coverage
# ============================================================


class TestOcrGeminiNoKey:
    """Cover line 160: raise RuntimeError('No Gemini OCR key configured')."""

    def test_no_key_raises(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_gemini

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        settings = _make_settings(
            extraction_api_key="",
            gemini_api_key="",
            google_api_key="",
        )
        with pytest.raises(RuntimeError, match="No Gemini OCR key"):
            _ocr_gemini(img, settings)


class TestOcrNvidiaReraise:
    """Cover line 243: non-429 HTTPStatusError re-raised on last attempt."""

    def test_non_429_reraises(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8")

        resp_500 = MagicMock()
        resp_500.status_code = 500
        err_500 = httpx.HTTPStatusError("500", request=MagicMock(), response=resp_500)
        resp_500.raise_for_status.side_effect = err_500
        mock_httpx = _make_mock_httpx(post_return=resp_500)

        settings = _make_settings(nvidia_build_api_key="nv-key")
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            pytest.raises(httpx.HTTPStatusError),
        ):
            _ocr_nvidia(img, settings, "nvidia_nim/test-model")


class TestOcrNvidiaLastAttempt429Reraises:
    """Cover line 243: last 429 attempt re-raises HTTPStatusError."""

    def test_last_429_reraises(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia, MAX_NVIDIA_RETRIES

        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8")

        # Build separate mock responses — each returns a fresh 429
        responses = []
        for _ in range(MAX_NVIDIA_RETRIES):
            r = MagicMock()
            r.status_code = 429
            err = httpx.HTTPStatusError("429", request=MagicMock(), response=r)
            r.raise_for_status.side_effect = err
            responses.append(r)

        mock_httpx = _make_mock_httpx(post_side_effect=responses)

        settings = _make_settings(nvidia_build_api_key="nv-key")
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.ocr.time"),
            pytest.raises(httpx.HTTPStatusError),
        ):
            _ocr_nvidia(img, settings, "nvidia_nim/test-model")


class TestOcrNvidiaZeroRetries:
    """Cover line 248: post-loop RuntimeError when MAX_NVIDIA_RETRIES patched to 0."""

    def test_zero_retries_raises(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        settings = _make_settings(nvidia_build_api_key="nv-key")
        with (
            patch("lab_manager.intake.ocr.MAX_NVIDIA_RETRIES", 0),
            pytest.raises(RuntimeError, match="NVIDIA OCR failed after retries"),
        ):
            _ocr_nvidia(img, settings, "nvidia_nim/test-model")


class TestOcrApiProviderChain:
    """Cover lines 264, 270-273, 275-277: _ocr_api provider chain with success/failure."""

    def test_first_provider_succeeds(self, tmp_path):
        """Cover lines 270-273: provider returns text successfully."""
        from lab_manager.intake.ocr import _ocr_api

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        mock_provider = MagicMock()
        mock_provider.extract_text.return_value = "OCR text result"

        settings = _make_settings(ocr_model="gemini-2.5-flash")
        with (
            patch(
                "lab_manager.intake.providers.more_ocr.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "lab_manager.intake.providers.more_ocr.OCR_PROVIDERS",
                {
                    "gemini_flash": "some.module:Class",
                    "mistral_ocr3": "some.module:Class2",
                },
            ),
        ):
            result = _ocr_api(img, settings)
            assert result == "OCR text result"

    def test_provider_not_in_registry_skipped(self, tmp_path):
        """Cover line 264: provider name not in OCR_PROVIDERS, continue."""
        from lab_manager.intake.ocr import _ocr_api

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        settings = _make_settings(
            ocr_model="gemini-2.5-flash",
            nvidia_build_api_key="",
            gemini_api_key="fake-key",
            extraction_api_key="fake-key",
        )
        # Empty registry -> all providers skipped -> falls to legacy Gemini
        with (
            patch(
                "lab_manager.intake.providers.more_ocr.OCR_PROVIDERS",
                {},
            ),
            patch("lab_manager.intake.ocr._ocr_gemini", return_value="legacy text"),
        ):
            result = _ocr_api(img, settings)
            assert result == "legacy text"

    def test_provider_raises_then_next_succeeds(self, tmp_path):
        """Cover lines 275-277: provider raises exception, fallback to next."""
        from lab_manager.intake.ocr import _ocr_api

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        mock_provider1 = MagicMock()
        mock_provider1.extract_text.side_effect = RuntimeError("API failure")
        mock_provider2 = MagicMock()
        mock_provider2.extract_text.return_value = "from second provider"

        settings = _make_settings(ocr_model="gemini-2.5-flash")
        with (
            patch(
                "lab_manager.intake.providers.more_ocr.get_provider",
                side_effect=[mock_provider1, mock_provider2],
            ),
            patch(
                "lab_manager.intake.providers.more_ocr.OCR_PROVIDERS",
                {"gemini_flash": "m:C1", "mistral_ocr3": "m:C2"},
            ),
        ):
            result = _ocr_api(img, settings)
            assert result == "from second provider"


class TestOcrApiLegacyGeminiWithPriorError:
    """Cover line 298: legacy Gemini path when prior chain errors exist."""

    def test_all_providers_fail_then_legacy_gemini_also_fails(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_api

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        mock_provider = MagicMock()
        mock_provider.extract_text.side_effect = RuntimeError("provider failed")

        settings = _make_settings(
            ocr_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        with (
            patch(
                "lab_manager.intake.providers.more_ocr.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "lab_manager.intake.providers.more_ocr.OCR_PROVIDERS",
                {"gemini_flash": "m:C1", "mistral_ocr3": "m:C2"},
            ),
            patch(
                "lab_manager.intake.ocr._ocr_gemini",
                side_effect=RuntimeError("gemini also failed"),
            ),
            pytest.raises(RuntimeError, match="All API OCR providers failed"),
        ):
            _ocr_api(img, settings)


class TestExtractTextFileNotFound:
    """Cover lines 347-348: FileNotFoundError returns empty string."""

    def test_file_not_found(self):
        from lab_manager.intake.ocr import extract_text_from_image

        with patch("lab_manager.intake.ocr.get_settings") as mock_settings:
            mock_settings.return_value = _make_settings(ocr_tier="local")
            with patch(
                "lab_manager.intake.ocr._ocr_local",
                side_effect=FileNotFoundError("no such file"),
            ):
                result = extract_text_from_image(Path("/nonexistent/file.png"))
                assert result == ""


# ============================================================
# routing.py coverage
# ============================================================


class TestRoutingMediumComplexity:
    """Cover lines 185-188: medium complexity branch."""

    def test_medium_complexity_route(self):
        from lab_manager.intake.routing import DocumentComplexity, route_document

        # Build text that hits the medium tier (0.30 <= composite < 0.60)
        # A medium-length text with moderate keyword density and a
        # non-simple/non-complex doc type will fall into medium range.
        text = "\n".join(
            [
                "Packing List",
                "Order Number: 12345",
                "Catalog Number: ABC-001",
                "Quantity: 5",
                "Lot Number: L999",
                "Ship Date: 2026-01-15",
            ]
            + [f"Line {i}" for i in range(15)]
        )

        decision = route_document(ocr_text=text, document_type="quote")
        assert decision.complexity == DocumentComplexity.medium
        assert decision.num_models == 2
        assert decision.skip_review is True
        assert "moderate" in decision.reason


class TestScoreLineCount:
    """Cover lines 93, 120, 129: score_complexity branches."""

    def test_invalid_doc_type_scores_medium(self):
        """Cover line 93: doc type not in VALID_DOC_TYPES."""
        from lab_manager.intake.routing import score_complexity

        scores = score_complexity("text", document_type="totally_made_up_type")
        assert scores["doc_type"] == 0.5

    def test_line_count_30_to_59(self):
        """Cover line 120: 30 <= line_count < 60 scores 0.7."""
        from lab_manager.intake.routing import score_complexity

        text = "\n".join(f"line {i}" for i in range(40))
        scores = score_complexity(text)
        assert scores["line_count"] == 0.7

    def test_item_count_hint_2_to_5(self):
        """Cover line 129: 1 < num_items_hint <= 5 scores 0.5."""
        from lab_manager.intake.routing import score_complexity

        scores = score_complexity("text", num_items_hint=3)
        assert scores["item_count"] == 0.5


# ============================================================
# extractor.py coverage
# ============================================================


class TestExtractorNvidiaLastAttempt429:
    """Cover lines 220-221, 227-228: _extract_nvidia last 429 attempt returns None."""

    def test_last_429_returns_none_with_error_log(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)

        # Only one attempt that gets a 429 on the last possible try
        resp_429 = MagicMock()
        resp_429.status_code = 429
        err_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=resp_429)
        resp_429.raise_for_status.side_effect = err_429

        # Provide exactly MAX_NVIDIA_RETRIES responses, all 429
        mock_httpx = _make_mock_httpx(post_side_effect=[resp_429] * 5)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor.time"),
            patch("lab_manager.intake.extractor.logger") as mock_logger,
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            result = _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b")
            assert result is None
            # Should have logged errors
            assert mock_logger.error.call_count >= 1


class TestExtractorNvidiaZeroRetries:
    """Cover lines 227-228: post-loop return None when MAX_NVIDIA_RETRIES patched to 0."""

    def test_zero_retries_returns_none(self):
        from lab_manager.intake.extractor import _extract_nvidia

        with (
            patch("lab_manager.intake.extractor.MAX_NVIDIA_RETRIES", 0),
            patch("lab_manager.intake.extractor.get_settings") as mock_gs,
            patch("lab_manager.intake.extractor.logger") as mock_logger,
        ):
            mock_gs.return_value = MagicMock(nvidia_build_api_key="nv-key")
            result = _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b")
            assert result is None
            # Should log the exhaustion error
            assert mock_logger.error.call_count >= 1


# ============================================================
# providers/__init__.py coverage
# ============================================================


class TestParseJsonResponseNoClosingFence:
    """Cover lines 65-66: markdown fence without closing ```."""

    def test_opening_fence_no_closing(self):
        from lab_manager.intake.providers import parse_json_response

        # Opening ```json but no closing ``` — should strip first line only
        text = '```json\n{"vendor": "Sigma"}'
        result = parse_json_response(text)
        assert result == {"vendor": "Sigma"}

    def test_opening_fence_with_closing(self):
        from lab_manager.intake.providers import parse_json_response

        text = '```json\n{"vendor": "Sigma"}\n```'
        result = parse_json_response(text)
        assert result == {"vendor": "Sigma"}


# ============================================================
# providers/qwen_vllm.py coverage
# ============================================================


class TestQwenVLLMProviderError:
    """Cover lines 60-62: QwenVLLMProvider.extract_text exception returns empty."""

    def test_openai_import_failure_returns_empty(self, tmp_path):
        from lab_manager.intake.providers.qwen_vllm import QwenVLLMProvider

        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8")

        provider = QwenVLLMProvider(base_url="http://localhost:99999/v1")
        # This will fail to connect, hitting the except branch (lines 60-62)
        result = provider.extract_text(str(img))
        assert result == ""


class TestGeminiAPIOCRProviderError:
    """Cover lines 139-141: GeminiAPIOCRProvider.extract_text exception returns empty."""

    def test_api_error_returns_empty(self, tmp_path):
        from lab_manager.intake.providers.qwen_vllm import GeminiAPIOCRProvider

        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG")

        provider = GeminiAPIOCRProvider(api_key="fake-key")
        # Patch the google.genai module so the local import picks up the mock
        with patch("google.genai.Client") as mock_client_cls:
            mock_client_cls.return_value.models.generate_content.side_effect = (
                RuntimeError("API error")
            )
            result = provider.extract_text(str(img))
            assert result == ""


# ============================================================
# pipeline.py coverage
# ============================================================


class TestPipelineExtractionNone:
    """Cover lines 98-100: extract_from_text returns None."""

    def test_extraction_returns_none(self, tmp_path, db_session):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "test_none.png"
        img.write_bytes(b"\x89PNG")

        with (
            patch("lab_manager.intake.pipeline.get_settings") as mock_gs,
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="Some OCR text",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=None,
            ),
        ):
            mock_gs.return_value = _make_settings(upload_dir=str(tmp_path / "uploads"))
            doc = process_document(img, db_session)
            assert doc.status == "needs_review"
            assert "no result returned" in (doc.review_notes or "")


class TestPipelineValidationIssuesInNotes:
    """Cover lines 171-174: validation issues appended to review_notes."""

    def test_validation_issues_recorded(self, tmp_path, db_session):
        from lab_manager.intake.pipeline import process_document

        img = tmp_path / "test_val.png"
        img.write_bytes(b"\x89PNG")

        extracted = ExtractedDocument(
            vendor_name="Sigma-Aldrich",
            document_type="packing_list",
            confidence=0.95,
        )

        validation_issues = [
            {
                "field": "vendor_name",
                "issue": "looks_like_address",
                "severity": "warning",
            }
        ]

        with (
            patch("lab_manager.intake.pipeline.get_settings") as mock_gs,
            patch(
                "lab_manager.intake.pipeline.extract_text_from_image",
                return_value="Some OCR text",
            ),
            patch(
                "lab_manager.intake.pipeline.extract_from_text",
                return_value=extracted,
            ),
            patch(
                "lab_manager.intake.validator.validate",
                return_value=validation_issues,
            ),
            patch(
                "lab_manager.services.vendor_normalize.normalize_vendor",
                return_value="Sigma-Aldrich",
            ),
            patch(
                "lab_manager.intake.extractor.extract_with_feedback",
                return_value=None,
            ),
        ):
            mock_gs.return_value = _make_settings(upload_dir=str(tmp_path / "uploads"))
            doc = process_document(img, db_session)
            assert doc.status == "needs_review"
            assert "Validation issues" in (doc.review_notes or "")
            assert "vendor_name" in (doc.review_notes or "")
