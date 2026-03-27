"""Tests for litellm_client service — model resolution and helper functions."""

from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.litellm_client import (
    _has_value,
    _first_value,
    get_client_params,
    resolve_model_name,
    response_text,
)


class TestHasValue:
    def test_non_empty_string(self):
        assert _has_value("hello") is True

    def test_empty_string(self):
        assert _has_value("") is False

    def test_whitespace_only(self):
        assert _has_value("   ") is False

    def test_none(self):
        assert _has_value(None) is False

    def test_int(self):
        assert _has_value(42) is False

    def test_bool(self):
        assert _has_value(True) is False


class TestFirstValue:
    def test_first_non_empty(self):
        assert _first_value("", "  ", "hello", "world") == "hello"

    def test_all_empty(self):
        assert _first_value("", None, "  ") == ""

    def test_first_value_stripped(self):
        assert _first_value("  value  ") == "value"

    def test_no_args(self):
        assert _first_value() == ""

    def test_non_string_values_skipped(self):
        assert _first_value(42, None, "", "found") == "found"

    def test_single_value(self):
        assert _first_value("only") == "only"


class TestResolveModelName:
    """Test resolve_model_name with mocked settings."""

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_slash_prefix_unchanged(self, mock_settings):
        """Models already containing '/' are returned as-is."""
        result = resolve_model_name("nvidia_nim/llama-3.2-90b")
        assert result == "nvidia_nim/llama-3.2-90b"
        mock_settings.assert_not_called()

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_prefix(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        result = resolve_model_name("gemini-2.5-flash")
        assert result == "gemini/gemini-2.5-flash"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_prefix_when_api_key_set(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="sk-test-key",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            result = resolve_model_name("gpt-4")
        assert result == "openai/gpt-4"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_prefix_when_key_set(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="nvapi-test",
        )
        with patch.dict("os.environ", {}, clear=False):
            result = resolve_model_name("some-model")
        assert result == "nvidia_nim/some-model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_default_gemini_when_no_keys(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            result = resolve_model_name("unknown-model")
        assert result == "gemini/unknown-model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_via_env_var(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}, clear=False):
            result = resolve_model_name("gpt-4o")
        assert result == "openai/gpt-4o"


class TestGetClientParams:
    """Test get_client_params for various provider routes."""

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_params(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="nvapi-test",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("nvidia_nim/llama-3.2")
        assert params["model"] == "nvidia_nim/llama-3.2"
        assert params["api_key"] == "nvapi-test"
        assert "api_base" in params

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_missing_key_raises(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            with pytest.raises(RuntimeError, match="NVIDIA Build API key"):
                get_client_params("nvidia_nim/llama-3.2")

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_params(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="sk-test",
            openai_api_key="",
            rag_base_url="https://api.example.com/v1",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert params["model"] == "openai/gpt-4"
        assert params["api_key"] == "sk-test"
        assert params["api_base"] == "https://api.example.com/v1"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_missing_key_raises(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="",
            openai_api_key="",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            with pytest.raises(RuntimeError, match="No API key found"):
                get_client_params("openai/gpt-4")

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_no_base_url(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="",
            openai_api_key="sk-openai",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert "api_base" not in params

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_params(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key-123",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("gemini/gemini-2.5-flash")
        assert params["model"] == "gemini/gemini-2.5-flash"
        assert params["api_key"] == "gemini-key-123"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_missing_key_raises(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="",
        )
        env = {
            k: v
            for k, v in __import__("os").environ.items()
            if k not in ("GEMINI_API_KEY", "EXTRACTION_API_KEY")
        }
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(RuntimeError, match="No Gemini API key"):
                get_client_params("gemini/gemini-2.5-flash")

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_via_env_var(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="",
        )
        with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
            params = get_client_params("gemini/gemini-2.5-flash")
        assert params["api_key"] == "env-key"


class TestResponseText:
    def test_string_content(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "  Hello World  "
        assert response_text(response) == "Hello World"

    def test_list_content_dict_items(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"},
        ]
        assert response_text(response) == "Hello\nWorld"

    def test_list_content_mixed_types(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        text_part = MagicMock()
        text_part.text = "from_object"
        response.choices[0].message.content = [
            {"type": "text", "text": "from_dict"},
            text_part,
        ]
        assert response_text(response) == "from_dict\nfrom_object"

    def test_list_content_with_empty_items(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = [
            {"type": "text", "text": "first"},
            {"type": "image", "text": "ignored"},
            {"type": "text", "text": ""},
            {"type": "text", "text": "last"},
        ]
        assert response_text(response) == "first\nlast"

    def test_non_string_non_list_content(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = 42
        assert response_text(response) == "42"

    def test_empty_string_content(self):
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = ""
        assert response_text(response) == ""
