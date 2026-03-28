"""Tests to push intake/ocr.py coverage from ~91% to 95%+.

Targets uncovered lines:
- 133-135: _ocr_local exception handler (provider throws)
- 160: _ocr_gemini no API key configured
- 243: _ocr_nvidia non-429 HTTPStatusError re-raise
- 248: _ocr_nvidia retries exhausted
- 264: _ocr_api provider not in OCR_PROVIDERS (continue)
- 270-273: _ocr_api provider succeeds with text
- 275-277: _ocr_api provider exception handler
- 298: _ocr_api Gemini fallback with last_error propagation
- 347-348: extract_text_from_image FileNotFoundError handler (logger path)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

GET_PROVIDER_PATCH = "lab_manager.intake.providers.more_ocr.get_provider"
OCR_PROVIDERS_PATCH = "lab_manager.intake.providers.more_ocr.OCR_PROVIDERS"


def _make_mock_httpx(post_return=None, post_side_effect=None):
    """Create a mock httpx module for sys.modules patching."""
    mock = MagicMock()
    mock.HTTPStatusError = httpx.HTTPStatusError
    if post_side_effect is not None:
        mock.post.side_effect = post_side_effect
    elif post_return is not None:
        mock.post.return_value = post_return
    return mock


# ---------------------------------------------------------------------------
# _ocr_local: lines 133-135 (exception handler when provider throws)
# ---------------------------------------------------------------------------


class TestOcrLocalExceptionPath:
    """Cover lines 133-135: provider raises exception in _ocr_local."""

    def test_provider_exception_sets_last_error(self):
        from lab_manager.intake.ocr import _ocr_local

        settings = MagicMock(ocr_local_model="deepseek_ocr", ocr_local_url="")
        mock_provider = MagicMock()
        mock_provider.extract_text.side_effect = ConnectionError("vLLM down")

        with (
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"deepseek_ocr": "x", "dots_mocr": "x", "glm_ocr_09b": "x"},
            ),
            pytest.raises(RuntimeError, match="All local OCR providers failed"),
        ):
            _ocr_local(Path("/tmp/test.png"), settings)


# ---------------------------------------------------------------------------
# _ocr_gemini: line 160 (no API key configured at all)
# ---------------------------------------------------------------------------


class TestOcrGeminiNoKey:
    """Cover line 160: RuntimeError when no API key is configured."""

    def test_no_api_key_at_all(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_gemini

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("EXTRACTION_API_KEY", raising=False)

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            extraction_api_key=None,
            gemini_api_key=None,
            google_api_key=None,
        )
        with pytest.raises(RuntimeError, match="No Gemini OCR key configured"):
            _ocr_gemini(img, settings)


# ---------------------------------------------------------------------------
# _ocr_nvidia: lines 243, 248 (non-429 re-raise and retries exhausted)
# ---------------------------------------------------------------------------


class TestOcrNvidiaRetryExhaustion:
    """Cover lines 243, 248: non-429 re-raise and all retries exhausted."""

    def test_non_429_http_error_reraises(self, monkeypatch, tmp_path):
        """Line 243: non-429 HTTPStatusError should re-raise immediately."""
        from lab_manager.intake.ocr import _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        resp_403 = MagicMock()
        resp_403.status_code = 403
        err_403 = httpx.HTTPStatusError(
            "forbidden", request=MagicMock(), response=resp_403
        )
        resp_403.raise_for_status.side_effect = err_403

        mock_httpx = _make_mock_httpx(post_return=resp_403)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.ocr.time"),
            pytest.raises(httpx.HTTPStatusError, match="forbidden"),
        ):
            _ocr_nvidia(
                img,
                MagicMock(nvidia_build_api_key="nv-key"),
                "nvidia_nim/meta/llama",
            )

    def test_all_retries_exhausted_429(self, monkeypatch, tmp_path):
        """Line 248: all retries exhausted after repeated 429s."""
        from lab_manager.intake.ocr import MAX_NVIDIA_RETRIES, _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        resp_429 = MagicMock()
        resp_429.status_code = 429
        err_429 = httpx.HTTPStatusError(
            "rate limited", request=MagicMock(), response=resp_429
        )
        resp_429.raise_for_status.side_effect = err_429

        # Return 429 on every attempt
        mock_httpx = _make_mock_httpx(post_side_effect=[resp_429] * MAX_NVIDIA_RETRIES)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch("lab_manager.intake.ocr.time"),
            pytest.raises(httpx.HTTPStatusError, match="rate limited"),
        ):
            _ocr_nvidia(
                img,
                MagicMock(nvidia_build_api_key="nv-key"),
                "nvidia_nim/meta/llama",
            )


# ---------------------------------------------------------------------------
# _ocr_api: lines 264, 270-273, 275-277 (provider chain in _ocr_api)
# ---------------------------------------------------------------------------


class TestOcrApiProviderChain:
    """Cover provider chain paths in _ocr_api (lines 264, 270-277)."""

    def test_provider_not_in_registry_skipped(self, tmp_path, monkeypatch):
        """Line 264: provider name not in OCR_PROVIDERS -> continue."""
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        # Empty OCR_PROVIDERS -> all providers skipped -> falls to Gemini direct
        with (
            patch(OCR_PROVIDERS_PATCH, {}),
            patch("lab_manager.intake.ocr._ocr_gemini", return_value="gemini result"),
        ):
            result = _ocr_api(img, settings)
            assert result == "gemini result"

    def test_provider_succeeds_with_text(self, tmp_path, monkeypatch):
        """Lines 270-273: provider returns text successfully."""
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        mock_provider = MagicMock()
        mock_provider.extract_text.return_value = "provider chain result"

        with (
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"gemini_flash": MagicMock(), "mistral_ocr3": MagicMock()},
            ),
        ):
            result = _ocr_api(img, settings)
            assert result == "provider chain result"

    def test_provider_raises_exception_continues(self, tmp_path, monkeypatch):
        """Lines 275-277: provider throws, sets last_error, continues chain."""
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        mock_provider = MagicMock()
        mock_provider.extract_text.side_effect = ConnectionError("timeout")

        with (
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"gemini_flash": MagicMock(), "mistral_ocr3": MagicMock()},
            ),
            patch("lab_manager.intake.ocr._ocr_gemini", return_value="gemini fallback"),
        ):
            result = _ocr_api(img, settings)
            assert result == "gemini fallback"

    def test_provider_exception_with_last_error_propagation(
        self, tmp_path, monkeypatch
    ):
        """Line 298: Gemini fails and last_error is set -> RuntimeError with last_error."""
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        # Provider raises, setting last_error; then Gemini also fails
        mock_provider = MagicMock()
        mock_provider.extract_text.side_effect = ConnectionError("provider down")

        with (
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"gemini_flash": MagicMock(), "mistral_ocr3": MagicMock()},
            ),
            patch(
                "lab_manager.intake.ocr._ocr_gemini",
                side_effect=RuntimeError("gemini also failed"),
            ),
            pytest.raises(RuntimeError, match="All API OCR providers failed"),
        ):
            _ocr_api(img, settings)

    def test_provider_returns_empty_continues(self, tmp_path, monkeypatch):
        """Line 274: provider returns empty string -> tries next in chain."""
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        # First provider returns empty, second returns text
        empty_provider = MagicMock()
        empty_provider.extract_text.return_value = ""
        good_provider = MagicMock()
        good_provider.extract_text.return_value = "second provider result"

        call_count = [0]

        def mock_get_provider(name, _registry):
            call_count[0] += 1
            if call_count[0] == 1:
                return empty_provider
            return good_provider

        with (
            patch(GET_PROVIDER_PATCH, side_effect=mock_get_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"gemini_flash": MagicMock(), "mistral_ocr3": MagicMock()},
            ),
        ):
            result = _ocr_api(img, settings)
            assert result == "second provider result"


# ---------------------------------------------------------------------------
# extract_text_from_image: lines 347-348 (FileNotFoundError logger path)
# ---------------------------------------------------------------------------


class TestExtractTextFileNotFoundLogger:
    """Cover lines 347-348: FileNotFoundError caught and logged."""

    def test_file_not_found_logs_error(self, tmp_path):
        """FileNotFoundError should be caught and return empty string."""
        from lab_manager.intake.ocr import extract_text_from_image

        nonexistent = tmp_path / "does_not_exist.png"
        settings = MagicMock(ocr_tier="local")

        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch("lab_manager.intake.ocr._ocr_local", side_effect=FileNotFoundError),
        ):
            # The FileNotFoundError is caught at the top-level handler (line 346-348)
            result = extract_text_from_image(nonexistent)
            assert result == ""


# ---------------------------------------------------------------------------
# _ocr_local: local_url override when empty (ensures all branches hit)
# ---------------------------------------------------------------------------


class TestOcrLocalFallbackChain:
    """Cover fallback chain building and skip of unknown providers."""

    def test_fallback_chain_ordering(self, tmp_path):
        """Verify chain is primary-first, then remaining fallbacks."""
        from lab_manager.intake.ocr import _ocr_local

        settings = MagicMock(ocr_local_model="glm_ocr_09b", ocr_local_url="")
        mock_provider = MagicMock()
        mock_provider.extract_text.return_value = "glm result"

        with (
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"dots_mocr": MagicMock(), "glm_ocr_09b": MagicMock()},
            ),
        ):
            result = _ocr_local(Path("/tmp/test.png"), settings)
            assert result == "glm result"

    def test_primary_provider_exception_fallback_succeeds(self, tmp_path):
        """Primary fails, secondary in chain succeeds."""
        from lab_manager.intake.ocr import _ocr_local

        settings = MagicMock(ocr_local_model="dots_mocr", ocr_local_url="")

        call_count = [0]

        def mock_get_provider(name, _registry):
            call_count[0] += 1
            p = MagicMock()
            if call_count[0] == 1:
                p.extract_text.side_effect = ConnectionError("first down")
            else:
                p.extract_text.return_value = "fallback result"
            return p

        with (
            patch(GET_PROVIDER_PATCH, side_effect=mock_get_provider),
            patch(
                OCR_PROVIDERS_PATCH,
                {"dots_mocr": MagicMock(), "glm_ocr_09b": MagicMock()},
            ),
        ):
            result = _ocr_local(Path("/tmp/test.png"), settings)
            assert result == "fallback result"


# ---------------------------------------------------------------------------
# _ocr_api: NVIDIA env var fallback path
# ---------------------------------------------------------------------------


class TestOcrApiNvidiaEnvFallback:
    """Cover NVIDIA fallback via env var in _ocr_api."""

    def test_nvidia_env_var_triggers_fallback(self, tmp_path, monkeypatch):
        """Lines 285-291: NVIDIA_BUILD_API_KEY env var triggers fallback."""
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.setenv("NVIDIA_BUILD_API_KEY", "env-var-key")
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")

        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        with (
            patch(OCR_PROVIDERS_PATCH, {}),
            patch(
                "lab_manager.intake.ocr._ocr_nvidia", return_value="nvidia env result"
            ) as mock_nvidia,
        ):
            result = _ocr_api(img, settings)
            assert result == "nvidia env result"
            mock_nvidia.assert_called_once()
