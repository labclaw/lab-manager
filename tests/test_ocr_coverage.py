"""Tests for intake/ocr.py — cover _response_text, _ocr_local, _ocr_gemini, _ocr_nvidia, _ocr_api, extract_text_from_image."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

GET_PROVIDER_PATCH = "lab_manager.intake.providers.more_ocr.get_provider"
OCR_PROVIDERS_PATCH = "lab_manager.intake.providers.more_ocr.OCR_PROVIDERS"


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
    def test_nvidia_prefix_true(self):
        from lab_manager.intake.ocr import _is_nvidia_model

        assert _is_nvidia_model("nvidia_nim/meta/llama-3.2-90b") is True

    def test_gemini_false(self):
        from lab_manager.intake.ocr import _is_nvidia_model

        assert _is_nvidia_model("gemini-2.5-flash") is False

    def test_non_string_false(self):
        from lab_manager.intake.ocr import _is_nvidia_model

        assert _is_nvidia_model(None) is False

    def test_empty_string_false(self):
        from lab_manager.intake.ocr import _is_nvidia_model

        assert _is_nvidia_model("") is False


class TestGetMimeType:
    def test_no_extension(self):
        from lab_manager.intake.ocr import _get_mime_type

        assert _get_mime_type("file") == "image/"

    def test_dot_only(self):
        from lab_manager.intake.ocr import _get_mime_type

        assert _get_mime_type(".") == "image/"


class TestGetOcrModel:
    def test_ocr_model_set(self):
        from lab_manager.intake.ocr import _get_ocr_model

        settings = MagicMock(
            ocr_model="nvidia_nim/meta/llama", extraction_model="gemini-2.5-flash"
        )
        assert _get_ocr_model(settings) == "nvidia_nim/meta/llama"

    def test_ocr_model_empty_uses_extraction(self):
        from lab_manager.intake.ocr import _get_ocr_model

        settings = MagicMock(ocr_model="", extraction_model="gemini-2.5-flash")
        assert _get_ocr_model(settings) == "gemini-2.5-flash"

    def test_ocr_model_none_uses_extraction(self):
        from lab_manager.intake.ocr import _get_ocr_model

        settings = MagicMock(ocr_model=None, extraction_model="gemini-2.5-flash")
        assert _get_ocr_model(settings) == "gemini-2.5-flash"


class TestResponseText:
    def test_text_attribute(self):
        from lab_manager.intake.ocr import _response_text

        resp = MagicMock()
        resp.text = "  hello world  "
        assert _response_text(resp) == "hello world"

    def test_text_attribute_none(self):
        from lab_manager.intake.ocr import _response_text

        resp = MagicMock()
        resp.text = None
        assert _response_text(resp) == ""

    def test_text_attribute_empty(self):
        from lab_manager.intake.ocr import _response_text

        resp = MagicMock()
        resp.text = "   "
        assert _response_text(resp) == ""

    def test_choices_string_content(self):
        from lab_manager.intake.ocr import _response_text

        msg = MagicMock()
        msg.content = "extracted text"
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.text = None
        resp.choices = [choice]
        assert _response_text(resp) == "extracted text"

    def test_choices_list_content_dict(self):
        from lab_manager.intake.ocr import _response_text

        choice = MagicMock()
        choice.message.content = [
            {"type": "text", "text": "part1"},
            {"type": "image", "url": "..."},
            {"type": "text", "text": "part2"},
        ]
        resp = MagicMock()
        resp.text = None
        resp.choices = [choice]
        assert _response_text(resp) == "part1\npart2"

    def test_choices_list_content_object(self):
        from lab_manager.intake.ocr import _response_text

        text_part = MagicMock()
        text_part.text = "object text"
        choice = MagicMock()
        choice.message.content = [text_part]
        resp = MagicMock()
        resp.text = None
        resp.choices = [choice]
        assert _response_text(resp) == "object text"

    def test_choices_list_content_non_text(self):
        from lab_manager.intake.ocr import _response_text

        choice = MagicMock()
        choice.message.content = [{"type": "image", "url": "..."}]
        resp = MagicMock()
        resp.text = None
        resp.choices = [choice]
        assert _response_text(resp) == ""

    def test_choices_non_string_content(self):
        from lab_manager.intake.ocr import _response_text

        choice = MagicMock()
        choice.message.content = 42
        resp = MagicMock()
        resp.text = None
        resp.choices = [choice]
        assert _response_text(resp) == "42"

    def test_choices_no_message(self):
        from lab_manager.intake.ocr import _response_text

        choice = MagicMock()
        choice.message = None
        resp = MagicMock()
        resp.text = None
        resp.choices = [choice]
        assert _response_text(resp) == ""

    def test_empty_choices(self):
        from lab_manager.intake.ocr import _response_text

        resp = MagicMock()
        resp.text = None
        resp.choices = []
        assert _response_text(resp) == ""


class TestOcrLocal:
    def test_unknown_provider_raises(self):
        from lab_manager.intake.ocr import _ocr_local

        settings = MagicMock(ocr_local_model="nonexistent_provider")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(OCR_PROVIDERS_PATCH, {}),
            pytest.raises(RuntimeError, match="Unknown local OCR provider"),
        ):
            _ocr_local(Path("/tmp/test.png"), settings)

    def test_provider_base_url_override(self):
        from lab_manager.intake.ocr import _ocr_local

        mock_provider = MagicMock()
        mock_provider.extract_text.return_value = "local OCR result"
        settings = MagicMock(
            ocr_local_model="deepseek_ocr", ocr_local_url="http://localhost:8000"
        )
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(OCR_PROVIDERS_PATCH, {"deepseek_ocr": MagicMock()}),
        ):
            result = _ocr_local(Path("/tmp/test.png"), settings)
            assert result == "local OCR result"
            assert mock_provider.base_url == "http://localhost:8000"

    def test_provider_no_base_url(self):
        from lab_manager.intake.ocr import _ocr_local

        mock_provider = MagicMock(spec=["extract_text"])
        mock_provider.extract_text.return_value = "result"
        settings = MagicMock(ocr_local_model="deepseek_ocr", ocr_local_url="")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(OCR_PROVIDERS_PATCH, {"deepseek_ocr": MagicMock()}),
        ):
            result = _ocr_local(Path("/tmp/test.png"), settings)
            assert result == "result"

    def test_empty_result_raises(self):
        from lab_manager.intake.ocr import _ocr_local

        mock_provider = MagicMock()
        mock_provider.extract_text.return_value = ""
        settings = MagicMock(ocr_local_model="deepseek_ocr", ocr_local_url="")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(GET_PROVIDER_PATCH, return_value=mock_provider),
            patch(OCR_PROVIDERS_PATCH, {"deepseek_ocr": MagicMock()}),
            pytest.raises(RuntimeError, match="empty text"),
        ):
            _ocr_local(Path("/tmp/test.png"), settings)


class TestOcrGemini:
    def test_success(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_gemini

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "  gemini ocr result  "
        mock_client.models.generate_content.return_value = mock_resp
        with (
            patch("lab_manager.intake.ocr.genai") as mock_genai,
            patch(
                "lab_manager.intake.ocr.get_settings",
                return_value=MagicMock(
                    extraction_api_key="", extraction_model="gemini-2.5-flash"
                ),
            ),
        ):
            mock_genai.Client.return_value = mock_client
            result = _ocr_gemini(
                img,
                MagicMock(extraction_api_key="", extraction_model="gemini-2.5-flash"),
            )
            assert result == "gemini ocr result"

    def test_no_api_key_raises(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_gemini

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        with pytest.raises(RuntimeError, match="No Gemini OCR key"):
            _ocr_gemini(
                img,
                MagicMock(extraction_api_key="", extraction_model="gemini-2.5-flash"),
            )

    def test_empty_result_raises(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_gemini

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_client.models.generate_content.return_value = mock_resp
        with (
            patch("lab_manager.intake.ocr.genai") as mock_genai,
            patch(
                "lab_manager.intake.ocr.get_settings",
                return_value=MagicMock(
                    extraction_api_key="", extraction_model="gemini-2.5-flash"
                ),
            ),
            pytest.raises(RuntimeError, match="empty text"),
        ):
            mock_genai.Client.return_value = mock_client
            _ocr_gemini(
                img,
                MagicMock(extraction_api_key="", extraction_model="gemini-2.5-flash"),
            )


class TestOcrNvidia:
    """Tests for _ocr_nvidia which does 'import httpx' internally."""

    def test_success(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "nvidia ocr result"}}]
        }
        mock_httpx = _make_mock_httpx(post_return=mock_resp)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch(
                "lab_manager.intake.ocr.get_settings",
                return_value=MagicMock(nvidia_build_api_key="nv-key"),
            ),
        ):
            result = _ocr_nvidia(
                img, MagicMock(nvidia_build_api_key="nv-key"), "nvidia_nim/meta/llama"
            )
            assert result == "nvidia ocr result"

    def test_no_api_key_raises(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        with pytest.raises(RuntimeError, match="No NVIDIA OCR key"):
            _ocr_nvidia(
                img, MagicMock(nvidia_build_api_key=""), "nvidia_nim/meta/llama"
            )

    def test_rate_limit_retry(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        resp_429 = MagicMock()
        resp_429.status_code = 429
        err_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=resp_429)
        resp_429.raise_for_status.side_effect = err_429
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {
            "choices": [{"message": {"content": "after retry"}}]
        }
        mock_httpx = _make_mock_httpx(post_side_effect=[resp_429, resp_ok])
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch(
                "lab_manager.intake.ocr.get_settings",
                return_value=MagicMock(nvidia_build_api_key="nv-key"),
            ),
            patch("lab_manager.intake.ocr.time"),
        ):
            result = _ocr_nvidia(
                img, MagicMock(nvidia_build_api_key="nv-key"), "nvidia_nim/meta/llama"
            )
            assert result == "after retry"

    def test_empty_choices_raises(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": []}
        mock_httpx = _make_mock_httpx(post_return=mock_resp)
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch(
                "lab_manager.intake.ocr.get_settings",
                return_value=MagicMock(nvidia_build_api_key="nv-key"),
            ),
            pytest.raises(RuntimeError, match="empty choices"),
        ):
            _ocr_nvidia(
                img, MagicMock(nvidia_build_api_key="nv-key"), "nvidia_nim/meta/llama"
            )

    def test_generic_error_wrapped(self, monkeypatch, tmp_path):
        from lab_manager.intake.ocr import _ocr_nvidia

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        mock_httpx = _make_mock_httpx(post_side_effect=Exception("timeout"))
        with (
            patch.dict("sys.modules", {"httpx": mock_httpx}),
            patch(
                "lab_manager.intake.ocr.get_settings",
                return_value=MagicMock(nvidia_build_api_key="nv-key"),
            ),
            pytest.raises(RuntimeError, match="NVIDIA OCR failed"),
        ):
            _ocr_nvidia(
                img, MagicMock(nvidia_build_api_key="nv-key"), "nvidia_nim/meta/llama"
            )


class TestOcrApi:
    def test_nvidia_model_direct(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_api

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(
            ocr_model="nvidia_nim/meta/llama",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="",
        )
        with patch(
            "lab_manager.intake.ocr._ocr_nvidia", return_value="nvidia result"
        ) as mock:
            assert _ocr_api(img, settings) == "nvidia result"
            mock.assert_called_once()

    def test_gemini_success(self, tmp_path):
        from lab_manager.intake.ocr import _ocr_api

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(
            ocr_model="", extraction_model="gemini-2.5-flash", nvidia_build_api_key=""
        )
        with patch("lab_manager.intake.ocr._ocr_gemini", return_value="gemini result"):
            assert _ocr_api(img, settings) == "gemini result"

    def test_gemini_fails_nvidia_fallback(self, tmp_path, monkeypatch):
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(
            ocr_model="",
            extraction_model="gemini-2.5-flash",
            nvidia_build_api_key="nv-key",
        )
        with (
            patch(
                "lab_manager.intake.ocr._ocr_gemini", side_effect=RuntimeError("fail")
            ),
            patch(
                "lab_manager.intake.ocr._ocr_nvidia", return_value="fallback result"
            ) as mock_nvidia,
        ):
            assert _ocr_api(img, settings) == "fallback result"
            mock_nvidia.assert_called_once()

    def test_gemini_fails_no_nvidia_key_raises(self, tmp_path, monkeypatch):
        from lab_manager.intake.ocr import _ocr_api

        monkeypatch.delenv("NVIDIA_BUILD_API_KEY", raising=False)
        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(
            ocr_model="", extraction_model="gemini-2.5-flash", nvidia_build_api_key=""
        )
        with (
            patch(
                "lab_manager.intake.ocr._ocr_gemini", side_effect=RuntimeError("fail")
            ),
            pytest.raises(RuntimeError, match="fail"),
        ):
            _ocr_api(img, settings)


class TestExtractTextFromImage:
    def test_tier_local(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="local")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch("lab_manager.intake.ocr._ocr_local", return_value="local result"),
        ):
            assert extract_text_from_image(img) == "local result"

    def test_tier_api(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="api")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch("lab_manager.intake.ocr._ocr_api", return_value="api result"),
        ):
            assert extract_text_from_image(img) == "api result"

    def test_tier_auto_local_succeeds(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="auto")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch("lab_manager.intake.ocr._ocr_local", return_value="local result"),
            patch("lab_manager.intake.ocr._ocr_api") as mock_api,
        ):
            assert extract_text_from_image(img) == "local result"
            mock_api.assert_not_called()

    def test_tier_auto_local_fails_falls_to_api(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="auto")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(
                "lab_manager.intake.ocr._ocr_local",
                side_effect=RuntimeError("local fail"),
            ),
            patch("lab_manager.intake.ocr._ocr_api", return_value="api fallback"),
        ):
            assert extract_text_from_image(img) == "api fallback"

    def test_tier_auto_local_returns_empty_falls_to_api(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="auto")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch("lab_manager.intake.ocr._ocr_local", return_value=""),
            patch("lab_manager.intake.ocr._ocr_api", return_value="api fallback"),
        ):
            assert extract_text_from_image(img) == "api fallback"

    def test_invalid_tier_defaults_to_auto(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="invalid_tier")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(
                "lab_manager.intake.ocr._ocr_local", side_effect=RuntimeError("fail")
            ),
            patch("lab_manager.intake.ocr._ocr_api", return_value="api result"),
        ):
            assert extract_text_from_image(img) == "api result"

    def test_file_not_found_returns_empty(self):
        from lab_manager.intake.ocr import extract_text_from_image

        with patch(
            "lab_manager.intake.ocr.get_settings",
            return_value=MagicMock(ocr_tier="local"),
        ):
            assert extract_text_from_image(Path("/nonexistent/path.png")) == ""

    def test_api_error_returns_empty(self, tmp_path):
        from google.genai import errors as genai_errors
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="api")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(
                "lab_manager.intake.ocr._ocr_api",
                side_effect=genai_errors.APIError(500, {"msg": "err"}, None),
            ),
        ):
            assert extract_text_from_image(img) == ""

    def test_generic_exception_returns_empty(self, tmp_path):
        from lab_manager.intake.ocr import extract_text_from_image

        img = tmp_path / "test.png"
        img.write_bytes(b"fake")
        settings = MagicMock(ocr_tier="api")
        with (
            patch("lab_manager.intake.ocr.get_settings", return_value=settings),
            patch(
                "lab_manager.intake.ocr._ocr_api",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            assert extract_text_from_image(img) == ""
