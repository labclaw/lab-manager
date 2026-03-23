"""Tests for LiteLLM client wrapper."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.litellm_client import (
    _first_value,
    _has_value,
    get_client_params,
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
            from lab_manager.services.litellm_client import create_completion

            result = create_completion(
                model="nvidia_nim/test-model",
                messages=[{"role": "user", "content": "hello"}],
            )
            assert result == mock_response
            mock_completion.assert_called_once()
