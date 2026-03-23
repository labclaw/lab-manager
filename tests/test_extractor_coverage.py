"""Tests for intake/extractor.py — cover _call_llm, _extract_nvidia, extract_from_text."""

import json
from unittest.mock import MagicMock, patch

import httpx

from lab_manager.intake.schemas import ExtractedDocument

SAMPLE_EXTRACTED = ExtractedDocument(
    vendor_name="Sigma-Aldrich",
    document_type="packing_list",
    po_number="PO-999",
    items=[{"catalog_number": "A1234", "quantity": 2}],
    confidence=0.9,
)

SAMPLE_OCR = "Sigma-Aldrich PO-999 Catalog A1234 Qty 2"


def _make_mock_httpx(post_return=None, post_side_effect=None):
    """Create a mock httpx module for sys.modules patching.
    
    Must include the real HTTPStatusError class since the source code
    does 'except httpx.HTTPStatusError as e:'.
    """
    mock = MagicMock()
    mock.HTTPStatusError = httpx.HTTPStatusError
    if post_side_effect is not None:
        mock.post.side_effect = post_side_effect
    elif post_return is not None:
        mock.post.return_value = post_return
    return mock


class TestIsNvidiaModel:
    def test_nvidia_prefix(self):
        from lab_manager.intake.extractor import _is_nvidia_model
        assert _is_nvidia_model("nvidia_nim/meta/llama-3.2-90b") is True

    def test_non_nvidia(self):
        from lab_manager.intake.extractor import _is_nvidia_model
        assert _is_nvidia_model("gemini-2.5-flash") is False


class TestCallLlm:
    def test_gemini_success(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SAMPLE_EXTRACTED
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        with (
            patch("lab_manager.intake.extractor.genai", mock_genai),
            patch("lab_manager.intake.extractor.instructor") as mock_inst,
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="",
            )
            mock_inst.from_genai.return_value = mock_client
            result = _call_llm(SAMPLE_OCR)
            assert isinstance(result, ExtractedDocument)

    def test_gemini_no_api_key_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        with patch("lab_manager.intake.extractor.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="",
            )
            assert _call_llm(SAMPLE_OCR) is None

    def test_gemini_retry_on_connection_error(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        with (
            patch("lab_manager.intake.extractor.genai", mock_genai),
            patch("lab_manager.intake.extractor.instructor") as mock_inst,
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor.time") as mock_time,
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="",
            )
            mock_inst.from_genai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = [
                ConnectionError("timeout"),
                SAMPLE_EXTRACTED,
            ]
            assert _call_llm(SAMPLE_OCR) is not None
            assert mock_time.sleep.call_count == 1

    def test_gemini_retry_exhausted_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        with (
            patch("lab_manager.intake.extractor.genai", mock_genai),
            patch("lab_manager.intake.extractor.instructor") as mock_inst,
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor.time"),
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="",
            )
            mock_inst.from_genai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = ConnectionError("timeout")
            assert _call_llm(SAMPLE_OCR) is None

    def test_gemini_api_error_falls_back_to_nvidia(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        from google.genai import errors as genai_errors
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        api_error = genai_errors.APIError(429, {"message": "quota"}, None)
        with (
            patch("lab_manager.intake.extractor.genai", mock_genai),
            patch("lab_manager.intake.extractor.instructor") as mock_inst,
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor._extract_nvidia") as mock_nvidia,
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="nv-key",
            )
            mock_inst.from_genai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = api_error
            mock_nvidia.return_value = SAMPLE_EXTRACTED
            assert _call_llm(SAMPLE_OCR) == SAMPLE_EXTRACTED
            mock_nvidia.assert_called_once()

    def test_gemini_api_error_no_nvidia_key_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        from google.genai import errors as genai_errors
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        mock_client = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        with (
            patch("lab_manager.intake.extractor.genai", mock_genai),
            patch("lab_manager.intake.extractor.instructor") as mock_inst,
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="",
            )
            mock_inst.from_genai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = genai_errors.APIError(
                429, {"message": "err"}, None
            )
            assert _call_llm(SAMPLE_OCR) is None

    def test_generic_exception_falls_back_to_nvidia(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_genai = MagicMock()
        mock_genai.Client.return_value = mock_client
        with (
            patch("lab_manager.intake.extractor.genai", mock_genai),
            patch("lab_manager.intake.extractor.instructor") as mock_inst,
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor._extract_nvidia") as mock_nvidia,
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="gemini-2.5-flash",
                extraction_api_key="",
                nvidia_build_api_key="nv-key",
            )
            mock_inst.from_genai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = RuntimeError("unexpected")
            mock_nvidia.return_value = SAMPLE_EXTRACTED
            assert _call_llm(SAMPLE_OCR) == SAMPLE_EXTRACTED

    def test_nvidia_model_direct(self, monkeypatch):
        from lab_manager.intake.extractor import _call_llm
        with (
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor._extract_nvidia") as mock_nvidia,
        ):
            mock_settings.return_value = MagicMock(
                extraction_model="nvidia_nim/meta/llama-3.2-90b-vision-instruct",
                nvidia_build_api_key="nv-key",
            )
            mock_nvidia.return_value = SAMPLE_EXTRACTED
            assert _call_llm(SAMPLE_OCR) == SAMPLE_EXTRACTED
            mock_nvidia.assert_called_once_with(
                SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
            )


class TestExtractNvidia:
    """Tests for _extract_nvidia which does 'import httpx' internally."""

    def test_success(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        raw_json = json.dumps(SAMPLE_EXTRACTED.model_dump())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": raw_json}}]}
        mock_httpx = _make_mock_httpx(post_return=mock_resp)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            result = _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b")
            assert result is not None
            assert result.vendor_name == "Sigma-Aldrich"

    def test_no_api_key_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        with patch("lab_manager.intake.extractor.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(nvidia_build_api_key="")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is None

    def test_rate_limit_retry_then_success(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        raw_json = json.dumps(SAMPLE_EXTRACTED.model_dump())
        resp_429 = MagicMock()
        resp_429.status_code = 429
        err_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=resp_429)
        resp_429.raise_for_status.side_effect = err_429
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"choices": [{"message": {"content": raw_json}}]}
        mock_httpx = _make_mock_httpx(post_side_effect=[resp_429, resp_ok])
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor.time"),
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is not None

    def test_rate_limit_all_retries_exhausted(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        err_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=resp_429)
        resp_429.raise_for_status.side_effect = err_429
        mock_httpx = _make_mock_httpx(post_return=resp_429)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
            patch("lab_manager.intake.extractor.time"),
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is None

    def test_markdown_fence_stripped(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        raw_json = "```json\n" + json.dumps(SAMPLE_EXTRACTED.model_dump()) + "\n```"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": raw_json}}]}
        mock_httpx = _make_mock_httpx(post_return=mock_resp)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is not None

    def test_http_error_non_429_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        resp_500 = MagicMock()
        resp_500.status_code = 500
        err_500 = httpx.HTTPStatusError("500", request=MagicMock(), response=resp_500)
        resp_500.raise_for_status.side_effect = err_500
        mock_httpx = _make_mock_httpx(post_return=resp_500)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is None

    def test_generic_exception_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        mock_httpx = _make_mock_httpx(post_side_effect=Exception("network error"))
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is None

    def test_invalid_json_returns_none(self, monkeypatch):
        from lab_manager.intake.extractor import _extract_nvidia
        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        mock_httpx = _make_mock_httpx(post_return=mock_resp)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.extractor.get_settings") as mock_settings,
        ):
            mock_settings.return_value = MagicMock(nvidia_build_api_key="nv-key")
            assert _extract_nvidia(SAMPLE_OCR, "nvidia_nim/meta/llama-3.2-90b") is None


class TestExtractFromText:
    def test_delegates_to_call_llm(self):
        from lab_manager.intake.extractor import extract_from_text
        with patch("lab_manager.intake.extractor._call_llm", return_value=SAMPLE_EXTRACTED):
            assert extract_from_text(SAMPLE_OCR) == SAMPLE_EXTRACTED

    def test_none_propagates(self):
        from lab_manager.intake.extractor import extract_from_text
        with patch("lab_manager.intake.extractor._call_llm", return_value=None):
            assert extract_from_text(SAMPLE_OCR) is None
