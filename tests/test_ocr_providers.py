"""Tests for OCR providers and tiered detection."""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Provider registry tests
# ---------------------------------------------------------------------------


class TestOCRProviderRegistry:
    def test_new_providers_registered(self):
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        assert "deepseek_ocr" in OCR_PROVIDERS
        assert "paddleocr_vl" in OCR_PROVIDERS
        assert "mistral_ocr3" in OCR_PROVIDERS

    def test_existing_providers_still_registered(self):
        from lab_manager.intake.providers.more_ocr import OCR_PROVIDERS

        for name in (
            "qwen3_vl",
            "gemini_flash",
            "gemini_api",
            "deepseek_vl",
            "glm_4v",
            "paddleocr",
            "mistral_pixtral",
            "claude_sonnet",
            "codex_gpt",
        ):
            assert name in OCR_PROVIDERS, f"Missing provider: {name}"

    def test_get_provider_unknown_raises(self):
        from lab_manager.intake.providers.more_ocr import get_provider

        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_model")

    def test_get_provider_instantiates_deepseek_ocr(self):
        from lab_manager.intake.providers.more_ocr import (
            DeepSeekOCRProvider,
            OCR_PROVIDERS,
            get_provider,
        )

        provider = get_provider("deepseek_ocr", OCR_PROVIDERS)
        assert isinstance(provider, DeepSeekOCRProvider)
        assert provider.name == "deepseek_ocr"
        assert provider.model_id == "deepseek-ai/DeepSeek-OCR"

    def test_get_provider_instantiates_paddleocr_vl(self):
        from lab_manager.intake.providers.more_ocr import (
            OCR_PROVIDERS,
            PaddleOCRVLProvider,
            get_provider,
        )

        provider = get_provider("paddleocr_vl", OCR_PROVIDERS)
        assert isinstance(provider, PaddleOCRVLProvider)
        assert provider.name == "paddleocr_vl"
        assert provider.model_id == "PaddlePaddle/PaddleOCR-VL"

    def test_get_provider_instantiates_mistral_ocr3(self):
        from lab_manager.intake.providers.more_ocr import (
            MistralOCR3Provider,
            OCR_PROVIDERS,
            get_provider,
        )

        provider = get_provider("mistral_ocr3", OCR_PROVIDERS)
        assert isinstance(provider, MistralOCR3Provider)
        assert provider.name == "mistral_ocr3"
        assert provider.model_id == "mistral-ocr-latest"


# ---------------------------------------------------------------------------
# DeepSeekOCRProvider tests
# ---------------------------------------------------------------------------


class TestDeepSeekOCRProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import DeepSeekOCRProvider

        p = DeepSeekOCRProvider()
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "deepseek-ai/DeepSeek-OCR"

    def test_custom_url(self):
        from lab_manager.intake.providers.more_ocr import DeepSeekOCRProvider

        p = DeepSeekOCRProvider(base_url="http://gpu:9000/v1")
        assert p.base_url == "http://gpu:9000/v1"

    @patch("lab_manager.intake.providers.more_ocr.Path")
    def test_extract_text_success(self, mock_path_cls):
        from lab_manager.intake.providers.more_ocr import DeepSeekOCRProvider

        mock_path_cls.return_value.read_bytes.return_value = b"fake-image"
        mock_path_cls.return_value.suffix = ".png"

        mock_msg = MagicMock()
        mock_msg.content = "Extracted OCR text here"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_response

            p = DeepSeekOCRProvider()
            result = p.extract_text("/tmp/test.png")
            assert result == "Extracted OCR text here"

    def test_extract_text_returns_empty_on_error(self):
        from lab_manager.intake.providers.more_ocr import DeepSeekOCRProvider

        p = DeepSeekOCRProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# PaddleOCRVLProvider tests
# ---------------------------------------------------------------------------


class TestPaddleOCRVLProvider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        p = PaddleOCRVLProvider()
        assert p.base_url == "http://localhost:8000/v1"
        assert p.model == "PaddlePaddle/PaddleOCR-VL"

    def test_extract_text_returns_empty_on_error(self):
        from lab_manager.intake.providers.more_ocr import PaddleOCRVLProvider

        p = PaddleOCRVLProvider(base_url="http://nonexistent:9999/v1")
        result = p.extract_text("/nonexistent/file.png")
        assert result == ""


# ---------------------------------------------------------------------------
# MistralOCR3Provider tests
# ---------------------------------------------------------------------------


class TestMistralOCR3Provider:
    def test_defaults(self):
        from lab_manager.intake.providers.more_ocr import MistralOCR3Provider

        p = MistralOCR3Provider()
        assert p.model == "mistral-ocr-latest"

    def test_no_api_key_returns_empty(self):
        from lab_manager.intake.providers.more_ocr import MistralOCR3Provider

        with patch.dict("os.environ", {}, clear=True):
            p = MistralOCR3Provider(api_key="")
            result = p.extract_text("/tmp/test.png")
            assert result == ""

    @patch("httpx.post")
    def test_extract_text_success(self, mock_post):
        from lab_manager.intake.providers.more_ocr import MistralOCR3Provider

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "pages": [
                {"markdown": "Page 1 content"},
                {"markdown": "Page 2 content"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        p = MistralOCR3Provider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"fake-image"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")

        assert result == "Page 1 content\n\nPage 2 content"

    @patch("httpx.post")
    def test_extract_text_api_error(self, mock_post):
        from lab_manager.intake.providers.more_ocr import MistralOCR3Provider

        mock_post.side_effect = Exception("API down")

        p = MistralOCR3Provider(api_key="test-key")
        with patch("lab_manager.intake.providers.more_ocr.Path") as mock_path:
            mock_path.return_value.read_bytes.return_value = b"fake"
            mock_path.return_value.suffix = ".png"
            result = p.extract_text("/tmp/test.png")

        assert result == ""


# ---------------------------------------------------------------------------
# Tiered detection tests
# ---------------------------------------------------------------------------


class TestTieredDetection:
    @patch("lab_manager.intake.ocr._ocr_local")
    @patch("lab_manager.intake.ocr._ocr_api")
    @patch("lab_manager.intake.ocr.get_settings")
    def test_tier_local_only(self, mock_settings, mock_api, mock_local):
        from lab_manager.intake.ocr import extract_text_from_image

        settings = MagicMock()
        settings.ocr_tier = "local"
        mock_settings.return_value = settings
        mock_local.return_value = "local result"

        result = extract_text_from_image(MagicMock())
        assert result == "local result"
        mock_local.assert_called_once()
        mock_api.assert_not_called()

    @patch("lab_manager.intake.ocr._ocr_local")
    @patch("lab_manager.intake.ocr._ocr_api")
    @patch("lab_manager.intake.ocr.get_settings")
    def test_tier_api_only(self, mock_settings, mock_api, mock_local):
        from lab_manager.intake.ocr import extract_text_from_image

        settings = MagicMock()
        settings.ocr_tier = "api"
        mock_settings.return_value = settings
        mock_api.return_value = "api result"

        result = extract_text_from_image(MagicMock())
        assert result == "api result"
        mock_api.assert_called_once()
        mock_local.assert_not_called()

    @patch("lab_manager.intake.ocr._ocr_local")
    @patch("lab_manager.intake.ocr._ocr_api")
    @patch("lab_manager.intake.ocr.get_settings")
    def test_tier_auto_local_success(self, mock_settings, mock_api, mock_local):
        from lab_manager.intake.ocr import extract_text_from_image

        settings = MagicMock()
        settings.ocr_tier = "auto"
        mock_settings.return_value = settings
        mock_local.return_value = "local result"

        result = extract_text_from_image(MagicMock())
        assert result == "local result"
        mock_local.assert_called_once()
        mock_api.assert_not_called()

    @patch("lab_manager.intake.ocr._ocr_local")
    @patch("lab_manager.intake.ocr._ocr_api")
    @patch("lab_manager.intake.ocr.get_settings")
    def test_tier_auto_fallback_to_api(self, mock_settings, mock_api, mock_local):
        from lab_manager.intake.ocr import extract_text_from_image

        settings = MagicMock()
        settings.ocr_tier = "auto"
        mock_settings.return_value = settings
        mock_local.side_effect = RuntimeError("vLLM not running")
        mock_api.return_value = "api fallback result"

        result = extract_text_from_image(MagicMock())
        assert result == "api fallback result"
        mock_local.assert_called_once()
        mock_api.assert_called_once()

    @patch("lab_manager.intake.ocr._ocr_local")
    @patch("lab_manager.intake.ocr._ocr_api")
    @patch("lab_manager.intake.ocr.get_settings")
    def test_tier_invalid_defaults_to_auto(self, mock_settings, mock_api, mock_local):
        from lab_manager.intake.ocr import extract_text_from_image

        settings = MagicMock()
        settings.ocr_tier = "invalid_tier"
        mock_settings.return_value = settings
        mock_local.return_value = "local result"

        result = extract_text_from_image(MagicMock())
        assert result == "local result"


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestOCRConfig:
    def test_new_settings_have_defaults(self):
        with patch.dict(
            "os.environ",
            {"AUTH_ENABLED": "false", "ADMIN_SECRET_KEY": ""},
            clear=False,
        ):
            from importlib import reload

            import lab_manager.config

            reload(lab_manager.config)
            from lab_manager.config import Settings

            s = Settings(
                auth_enabled=False,
                _env_file=None,
            )
            assert s.ocr_tier == "auto"
            assert s.ocr_local_model == "deepseek_ocr"
            assert s.ocr_local_url == "http://localhost:8000/v1"
            assert s.mistral_api_key == ""

    def test_valid_tiers(self):
        from lab_manager.intake.ocr import _VALID_TIERS

        assert "local" in _VALID_TIERS
        assert "api" in _VALID_TIERS
        assert "auto" in _VALID_TIERS
