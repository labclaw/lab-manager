"""Tests for LiteLLM client wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from lab_manager.services.litellm_client import (
    _first_value,
    _has_value,
    create_completion,
    get_client_params,
    load_litellm_config,
    resolve_model_name,
    response_text,
)


class TestHasValue:
    """Tests for _has_value helper."""

    def test_non_empty_string(self):
        assert _has_value("hello") is True

    def test_empty_string(self):
        assert _has_value("") is False

    def test_whitespace_only(self):
        assert _has_value("   ") is False

    def test_non_string(self):
        assert _has_value(123) is False
        assert _has_value(None) is False
        assert _has_value([]) is False


class TestFirstValue:
    """Tests for _first_value helper."""

    def test_returns_first_non_empty(self):
        assert _first_value("", "hello", "world") == "hello"

    def test_all_empty(self):
        assert _first_value("", None, "   ") == ""

    def test_strips_whitespace(self):
        assert _first_value("  hello  ") == "hello"


class TestResolveModelName:
    """Tests for resolve_model_name function."""

    def test_already_prefixed_gemini(self):
        """Models with / prefix are passed through."""
        assert (
            resolve_model_name("gemini/gemini-2.5-flash") == "gemini/gemini-2.5-flash"
        )

    def test_already_prefixed_openai(self):
        assert resolve_model_name("openai/gpt-4") == "openai/gpt-4"

    def test_already_prefixed_nvidia(self):
        assert (
            resolve_model_name("nvidia_nim/meta/llama-3.2-90b")
            == "nvidia_nim/meta/llama-3.2-90b"
        )

    def test_gemini_model_auto_prefix(self):
        """Gemini models get gemini/ prefix."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            assert resolve_model_name("gemini-2.5-flash") == "gemini/gemini-2.5-flash"

    def test_non_gemini_resolves_to_openai_with_api_key(self):
        """Non-gemini model with OpenAI API key gets openai/ prefix."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="sk-test-key",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(
                os.environ,
                {
                    "RAG_BASE_URL": "",
                    "RAG_API_KEY": "",
                    "OPENAI_API_KEY": "",
                },
                clear=False,
            ):
                assert resolve_model_name("gpt-4") == "openai/gpt-4"

    def test_non_gemini_resolves_to_openai_via_env(self):
        """Non-gemini model with env var OPENAI_API_KEY gets openai/ prefix."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(
                os.environ,
                {
                    "RAG_BASE_URL": "",
                    "RAG_API_KEY": "",
                    "OPENAI_API_KEY": "sk-env-key",
                },
                clear=False,
            ):
                assert resolve_model_name("gpt-4") == "openai/gpt-4"

    def test_non_gemini_resolves_to_nvidia_with_nvidia_key(self):
        """Non-gemini model with NVIDIA key but no OpenAI key gets nvidia_nim/ prefix."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="nvapi-test",
            )
            with patch.dict(
                os.environ,
                {
                    "RAG_BASE_URL": "",
                    "RAG_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "NVIDIA_BUILD_API_KEY": "",
                },
                clear=False,
            ):
                assert resolve_model_name("llama-3.2-90b") == "nvidia_nim/llama-3.2-90b"

    def test_non_gemini_resolves_to_nvidia_via_env(self):
        """Non-gemini model with NVIDIA env var gets nvidia_nim/ prefix."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(
                os.environ,
                {
                    "RAG_BASE_URL": "",
                    "RAG_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "NVIDIA_BUILD_API_KEY": "nvapi-env-key",
                },
                clear=False,
            ):
                assert resolve_model_name("llama-3.2-90b") == "nvidia_nim/llama-3.2-90b"

    def test_non_gemini_defaults_to_gemini(self):
        """Non-gemini model with no API keys defaults to gemini/ prefix."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(
                os.environ,
                {
                    "RAG_BASE_URL": "",
                    "RAG_API_KEY": "",
                    "OPENAI_API_KEY": "",
                    "NVIDIA_BUILD_API_KEY": "",
                },
                clear=False,
            ):
                assert resolve_model_name("some-model") == "gemini/some-model"


class TestGetClientParams:
    """Tests for get_client_params function."""

    def test_nvidia_nim_params(self):
        """NVIDIA NIM models get correct API base."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                nvidia_build_api_key="nvapi-test",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="",
                extraction_api_key="",
            )
            with patch.dict(os.environ, {"NVIDIA_BUILD_API_KEY": ""}, clear=False):
                params = get_client_params(
                    "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
                )
                assert (
                    params["model"] == "nvidia_nim/meta/llama-3.2-90b-vision-instruct"
                )
                assert params["api_key"] == "nvapi-test"
                assert params["api_base"] == "https://integrate.api.nvidia.com/v1"

    def test_nvidia_nim_no_key_raises(self):
        """Missing NVIDIA API key raises RuntimeError."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                nvidia_build_api_key="",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="",
            )
            with patch.dict(os.environ, {"NVIDIA_BUILD_API_KEY": ""}, clear=False):
                with pytest.raises(RuntimeError, match="NVIDIA Build API key"):
                    get_client_params("nvidia_nim/meta/llama-3.2-90b-vision-instruct")

    def test_openai_params(self):
        """OpenAI models get correct params."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="rag-test-key",
                rag_base_url="https://custom.api.com/v1",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            params = get_client_params("openai/gpt-4")
            assert params["model"] == "openai/gpt-4"
            assert params["api_key"] == "rag-test-key"
            assert params["api_base"] == "https://custom.api.com/v1"

    def test_openai_no_key_raises(self):
        """Missing OpenAI API key raises RuntimeError."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="",
                rag_base_url="",
                nvidia_build_api_key="",
            )
            with patch.dict(
                os.environ,
                {"RAG_API_KEY": "", "OPENAI_API_KEY": ""},
                clear=False,
            ):
                with pytest.raises(RuntimeError, match="No API key found"):
                    get_client_params("openai/gpt-4")

    def test_openai_no_base_url(self):
        """OpenAI params without custom base_url omits api_base."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_api_key="rag-key",
                rag_base_url="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(os.environ, {"RAG_BASE_URL": ""}, clear=False):
                params = get_client_params("openai/gpt-4")
                assert params["model"] == "openai/gpt-4"
                assert params["api_key"] == "rag-key"
                assert "api_base" not in params

    def test_gemini_params(self):
        """Gemini models use extraction_api_key."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                extraction_api_key="gem-test-key",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
                params = get_client_params("gemini/gemini-2.5-flash")
                assert params["model"] == "gemini/gemini-2.5-flash"
                assert params["api_key"] == "gem-test-key"

    def test_gemini_no_key_raises(self):
        """Missing Gemini API key raises RuntimeError."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                extraction_api_key="",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
                with pytest.raises(RuntimeError, match="No Gemini API key found"):
                    get_client_params("gemini/gemini-2.5-flash")

    def test_gemini_key_from_env(self):
        """Gemini models use GEMINI_API_KEY from env as fallback."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                extraction_api_key="",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(os.environ, {"GEMINI_API_KEY": "env-gem-key"}, clear=False):
                params = get_client_params("gemini/gemini-2.5-flash")
                assert params["api_key"] == "env-gem-key"


class TestResponseText:
    """Tests for response_text extraction."""

    def test_string_content(self):
        """String content is stripped."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "  hello world  "
        assert response_text(response) == "hello world"

    def test_list_content_text_type(self):
        """List content with text type is joined."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": "world"},
        ]
        assert response_text(response) == "hello\nworld"

    def test_list_content_mixed(self):
        """List content with text attribute works."""
        response = MagicMock()
        response.choices = [MagicMock()]
        text_part = MagicMock()
        text_part.text = "hello"
        response.choices[0].message.content = [text_part]
        assert response_text(response) == "hello"

    def test_non_string_non_list_content(self):
        """Non-string, non-list content falls through to str()."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = 42
        assert response_text(response) == "42"

    def test_list_content_filters_empty_parts(self):
        """List content with empty text parts are filtered out."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = [
            {"type": "text", "text": "hello"},
            {"type": "text", "text": ""},
            {"type": "text", "text": "world"},
        ]
        assert response_text(response) == "hello\nworld"

    def test_list_content_non_text_type_skipped(self):
        """List items with type != 'text' and no .text attr are skipped."""
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = [
            {"type": "image", "url": "http://example.com"},
            {"type": "text", "text": "hello"},
        ]
        assert response_text(response) == "hello"


class TestCreateCompletion:
    """Tests for create_completion function."""

    @patch("lab_manager.services.litellm_client.completion")
    def test_basic_completion(self, mock_completion):
        """Basic completion call works."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_completion.return_value = mock_response

        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                nvidia_build_api_key="nvapi-test",
                rag_api_key="",
                rag_base_url="",
                openai_api_key="",
                extraction_api_key="",
            )
            result = create_completion(
                model="nvidia_nim/test-model",
                messages=[{"role": "user", "content": "hello"}],
            )
            assert result == mock_response
            mock_completion.assert_called_once()

    @patch("lab_manager.services.litellm_client.completion")
    def test_completion_passes_kwargs(self, mock_completion):
        """Extra kwargs are passed through to completion call."""
        mock_completion.return_value = MagicMock()
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                nvidia_build_api_key="nvapi-test",
                rag_api_key="",
                rag_base_url="",
                openai_api_key="",
                extraction_api_key="",
            )
            create_completion(
                model="nvidia_nim/test-model",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7,
                max_tokens=100,
                top_p=0.9,
            )
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 100
            assert call_kwargs["top_p"] == 0.9


class TestLoadLitellmConfig:
    """Tests for load_litellm_config function."""

    def test_file_not_found(self):
        """Returns None when config file does not exist."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                litellm_config_path="/nonexistent/path/litellm_config.yaml"
            )
            result = load_litellm_config()
            assert result is None

    def test_loads_yaml_successfully(self):
        """Returns parsed YAML when config file exists."""
        yaml_content = "models:\n  - gemini-2.5-flash\n"
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(litellm_config_path=None)
            with patch("builtins.open", mock_open(read_data=yaml_content)):
                with patch(
                    "yaml.safe_load", return_value={"models": ["gemini-2.5-flash"]}
                ):
                    result = load_litellm_config()
                    assert result == {"models": ["gemini-2.5-flash"]}

    def test_yaml_parse_error(self):
        """Returns None when YAML parsing fails."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(litellm_config_path=None)
            with patch("builtins.open", mock_open(read_data="invalid: yaml:")):
                with patch("yaml.safe_load", side_effect=Exception("YAML error")):
                    result = load_litellm_config()
                    assert result is None

    def test_custom_config_path(self):
        """Uses custom config path from settings."""
        with patch("lab_manager.services.litellm_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                litellm_config_path="/custom/path/config.yaml"
            )
            with patch("builtins.open", mock_open(read_data="key: value")) as m_open:
                with patch("yaml.safe_load", return_value={"key": "value"}):
                    result = load_litellm_config()
                    m_open.assert_called_with("/custom/path/config.yaml")
                    assert result == {"key": "value"}
