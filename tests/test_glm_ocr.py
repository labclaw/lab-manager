"""Tests for dots.mocr, GLM-OCR 0.9B, PaddleOCR-VL 1.5, and updated fallback chains."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock registry used by fallback chain tests
_MOCK_REGISTRY = {
    "dots_mocr": "mock",
    "glm_ocr_09b": "mock",
    "gemini_flash": "mock",
}


# ---------------------------------------------------------------------------
# DotsMOCRProvider tests
# ---------------------------------------------------------------------------


class TestDotsMOCRProvider:
    def test_registered_in_providers(self):
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        assert "dots_mocr" in OCR_PROVIDERS

    def test_is_first_in_registry(self):
        """dots.mocr should be the first provider in registry ordering."""
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        keys = list(OCR_PROVIDERS.keys())
        assert keys[0] == "dots_mocr"

    def test_instantiate_via_get_provider(self):
        from lab_manager.intake.providers.more_ocr import (
            DotsMOCRProvider,
            OCR_PROVIDERS,
            get_provider,
        )

        provider = get_provider("dots_mocr", OCR_PROVIDERS)
        assert isinstance(provider, DotsMOCRProvider)
        assert provider.name == "dots_mocr"
        assert provider.model_id == "rednote-hilab/dots.mocr"

    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        p = DotsMOCRProvider()
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "rednote-hilab/dots.mocr"

    def test_custom_params(self):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        p = DotsMOCRProvider(base_url="http://gpu:9000/v1", model="custom-model")
        assert p.base_url == "http://gpu:9000/v1"
        assert p.model == "custom-model"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"fake-image"
        mock_path_cls.return_value.suffix = ".png"

        mock_msg = MagicMock()
        mock_msg.content = "dots.mocr extracted text"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = DotsMOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "dots.mocr extracted text"

            # Verify correct model is used
            call_kwargs = mock_client.chat.completions.create.call_args
            assert call_kwargs.kwargs["model"] == "rednote-hilab/dots.mocr"

    def test_extract_text_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import DotsMOCRProvider

        p = DotsMOCRProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# GLMOCRDedicatedProvider tests
# ---------------------------------------------------------------------------


class TestGLMOCRDedicatedProvider:
    def test_registered_in_providers(self):
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        assert "glm_ocr_09b" in OCR_PROVIDERS

    def test_instantiate_via_get_provider(self):
        from lab_manager.intake.providers.more_ocr import (
            GLMOCRDedicatedProvider,
            OCR_PROVIDERS,
            get_provider,
        )

        provider = get_provider("glm_ocr_09b", OCR_PROVIDERS)
        assert isinstance(provider, GLMOCRDedicatedProvider)
        assert provider.name == "glm_ocr_09b"
        assert provider.model_id == "zai-org/GLM-OCR"

    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        p = GLMOCRDedicatedProvider()
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "zai-org/GLM-OCR"
        assert p.mode == "vllm"
        assert p.api_key is None

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_vllm_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"fake-image"
        mock_path_cls.return_value.suffix = ".png"

        mock_msg = MagicMock()
        mock_msg.content = "GLM-OCR extracted text"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRDedicatedProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "GLM-OCR extracted text"

    def test_extract_text_vllm_error_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        p = GLMOCRDedicatedProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_api_mode_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        mock_path_cls.return_value.read_bytes.return_value = b"fake-image"
        mock_path_cls.return_value.suffix = ".jpg"

        mock_msg = MagicMock()
        mock_msg.content = "API OCR result"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = GLMOCRDedicatedProvider(mode="api", api_key="test-zai-key")
            result = p.extract_text("/tmp/test.jpg")
            assert result == "API OCR result"

            # Verify Z.ai API endpoint is used
            mock_openai.assert_called_once_with(
                base_url="https://open.bigmodel.cn/api/paas/v4",
                api_key="test-zai-key",
            )
            # Verify model name for API mode
            call_kwargs = mock_client.chat.completions.create.call_args
            assert call_kwargs.kwargs["model"] == "glm-ocr"

    def test_extract_text_api_no_key_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import GLMOCRDedicatedProvider

        with patch.dict(
            "os.environ",
            {"ZAI_API_KEY": "", "ZHIPU_API_KEY": ""},
            clear=False,
        ):
            p = GLMOCRDedicatedProvider(mode="api", api_key="")
            result = p.extract_text("/tmp/test.png")
            assert result == ""


# ---------------------------------------------------------------------------
# PaddleOCRVL15Provider tests
# ---------------------------------------------------------------------------


class TestPaddleOCRVL15Provider:
    def test_registered_in_providers(self):
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        assert "paddleocr_vl_15" in OCR_PROVIDERS

    def test_instantiate_via_get_provider(self):
        from lab_manager.intake.providers.more_ocr import (
            OCR_PROVIDERS,
            PaddleOCRVL15Provider,
            get_provider,
        )

        provider = get_provider("paddleocr_vl_15", OCR_PROVIDERS)
        assert isinstance(provider, PaddleOCRVL15Provider)
        assert provider.name == "paddleocr_vl_15"
        assert provider.model_id == "PaddlePaddle/PaddleOCR-VL-1.5"

    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        p = PaddleOCRVL15Provider()
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "PaddlePaddle/PaddleOCR-VL-1.5"

    def test_extract_text_returns_empty_on_error(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVL15Provider

        p = PaddleOCRVL15Provider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# Fallback chain tests
# ---------------------------------------------------------------------------


class TestLocalFallbackChain:
    def test_chain_constants_defined(self):
        from lab_manager.intake.ocr import LOCAL_FALLBACK_CHAIN

        assert LOCAL_FALLBACK_CHAIN == ["dots_mocr", "glm_ocr_09b", "gemini_flash"]

    def test_api_chain_constants_defined(self):
        from lab_manager.intake.ocr import API_FALLBACK_CHAIN

        assert API_FALLBACK_CHAIN == ["gemini_flash", "mistral_ocr3"]

    @patch("lab_manager.intake.providers.more_ocr.get_provider")
    @patch("lab_manager.intake.providers.more_ocr.OCR_PROVIDERS", _MOCK_REGISTRY)
    def test_local_primary_succeeds_no_fallback(self, mock_get_provider):
        from lab_manager.intake.ocr import _ocr_local

        mock_provider = MagicMock()
        mock_provider.extract_text.return_value = "dots.mocr result"
        mock_get_provider.return_value = mock_provider

        settings = MagicMock(ocr_local_model="dots_mocr", ocr_local_url="")
        result = _ocr_local(Path("/tmp/test.png"), settings)

        assert result == "dots.mocr result"
        # Should only call get_provider once (primary succeeded)
        mock_get_provider.assert_called_once()

    @patch("lab_manager.intake.providers.more_ocr.get_provider")
    @patch("lab_manager.intake.providers.more_ocr.OCR_PROVIDERS", _MOCK_REGISTRY)
    def test_local_primary_fails_fallback_succeeds(self, mock_get_provider):
        from lab_manager.intake.ocr import _ocr_local

        fail_provider = MagicMock()
        fail_provider.extract_text.return_value = ""

        success_provider = MagicMock()
        success_provider.extract_text.return_value = "GLM-OCR fallback result"

        mock_get_provider.side_effect = [fail_provider, success_provider]

        settings = MagicMock(ocr_local_model="dots_mocr", ocr_local_url="")
        result = _ocr_local(Path("/tmp/test.png"), settings)

        assert result == "GLM-OCR fallback result"
        assert mock_get_provider.call_count == 2

    @patch("lab_manager.intake.providers.more_ocr.get_provider")
    @patch("lab_manager.intake.providers.more_ocr.OCR_PROVIDERS", _MOCK_REGISTRY)
    def test_local_all_fail_raises(self, mock_get_provider):
        from lab_manager.intake.ocr import _ocr_local

        fail_provider = MagicMock()
        fail_provider.extract_text.return_value = ""
        mock_get_provider.return_value = fail_provider

        settings = MagicMock(ocr_local_model="dots_mocr", ocr_local_url="")

        with pytest.raises(RuntimeError, match="All local OCR providers failed"):
            _ocr_local(Path("/tmp/test.png"), settings)

    @patch("lab_manager.intake.providers.more_ocr.get_provider")
    @patch("lab_manager.intake.providers.more_ocr.OCR_PROVIDERS", _MOCK_REGISTRY)
    def test_local_exception_triggers_fallback(self, mock_get_provider):
        from lab_manager.intake.ocr import _ocr_local

        error_provider = MagicMock()
        error_provider.extract_text.side_effect = ConnectionError("vLLM down")

        success_provider = MagicMock()
        success_provider.extract_text.return_value = "fallback result"

        mock_get_provider.side_effect = [error_provider, success_provider]

        settings = MagicMock(ocr_local_model="dots_mocr", ocr_local_url="")
        result = _ocr_local(Path("/tmp/test.png"), settings)

        assert result == "fallback result"

    @patch("lab_manager.intake.providers.more_ocr.get_provider")
    @patch("lab_manager.intake.providers.more_ocr.OCR_PROVIDERS", _MOCK_REGISTRY)
    def test_local_custom_primary_then_fallback(self, mock_get_provider):
        """When primary is glm_ocr_09b, chain should be glm_ocr_09b -> dots_mocr -> gemini_flash."""
        from lab_manager.intake.ocr import _ocr_local

        fail_provider = MagicMock()
        fail_provider.extract_text.return_value = ""

        success_provider = MagicMock()
        success_provider.extract_text.return_value = "dots.mocr result"

        mock_get_provider.side_effect = [fail_provider, success_provider]

        settings = MagicMock(ocr_local_model="glm_ocr_09b", ocr_local_url="")
        result = _ocr_local(Path("/tmp/test.png"), settings)

        assert result == "dots.mocr result"
        # glm_ocr_09b failed, then dots_mocr succeeded
        assert mock_get_provider.call_count == 2


# ---------------------------------------------------------------------------
# Config default tests
# ---------------------------------------------------------------------------


class TestOCRConfigDefaults:
    def test_default_local_model_is_dots_mocr(self):
        """Config default should be dots_mocr."""
        with patch.dict(
            "os.environ",
            {"AUTH_ENABLED": "false", "ADMIN_SECRET_KEY": ""},
            clear=True,
        ):
            from importlib import reload

            import lab_manager.config

            reload(lab_manager.config)
            from lab_manager.config import Settings

            s = Settings(auth_enabled=False, _env_file=None)
            assert s.ocr_local_model == "dots_mocr"

    def test_default_model_exists_in_registry(self):
        """The default config value must exist in OCR_PROVIDERS."""
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        with patch.dict(
            "os.environ",
            {"AUTH_ENABLED": "false", "ADMIN_SECRET_KEY": ""},
            clear=True,
        ):
            from importlib import reload

            import lab_manager.config

            reload(lab_manager.config)
            from lab_manager.config import Settings

            s = Settings(auth_enabled=False, _env_file=None)
            assert s.ocr_local_model in OCR_PROVIDERS
