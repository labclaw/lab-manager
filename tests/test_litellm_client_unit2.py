"""Comprehensive unit tests for litellm_client service.

Covers all public functions: _has_value, _first_value, resolve_model_name,
get_client_params, create_completion, response_text, load_litellm_config.
Tests model resolution, API key management, provider routing, error handling,
response parsing, config loading, and edge cases.
"""

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


# ---------------------------------------------------------------------------
# _has_value
# ---------------------------------------------------------------------------


class TestHasValue:
    """Tests for _has_value helper."""

    def test_regular_string(self):
        assert _has_value("hello") is True

    def test_string_with_spaces(self):
        assert _has_value("  hello  ") is True

    def test_empty_string(self):
        assert _has_value("") is False

    def test_whitespace_only(self):
        assert _has_value("   \t\n  ") is False

    def test_none(self):
        assert _has_value(None) is False

    def test_integer(self):
        assert _has_value(0) is False

    def test_float(self):
        assert _has_value(3.14) is False

    def test_boolean_true(self):
        assert _has_value(True) is False

    def test_boolean_false(self):
        assert _has_value(False) is False

    def test_list(self):
        assert _has_value(["not", "empty"]) is False

    def test_dict(self):
        assert _has_value({"key": "value"}) is False

    def test_empty_list(self):
        assert _has_value([]) is False

    def test_empty_dict(self):
        assert _has_value({}) is False

    def test_single_space(self):
        assert _has_value(" ") is False

    def test_tab_character(self):
        assert _has_value("\t") is False

    def test_newline_character(self):
        assert _has_value("\n") is False


# ---------------------------------------------------------------------------
# _first_value
# ---------------------------------------------------------------------------


class TestFirstValue:
    """Tests for _first_value helper."""

    def test_returns_first_non_empty_string(self):
        assert _first_value("", "  ", "hello", "world") == "hello"

    def test_all_empty_returns_empty(self):
        assert _first_value("", None, "  ") == ""

    def test_no_args_returns_empty(self):
        assert _first_value() == ""

    def test_strips_whitespace(self):
        assert _first_value("  value  ") == "value"

    def test_non_string_values_skipped(self):
        assert _first_value(42, None, "", "found") == "found"

    def test_single_valid_value(self):
        assert _first_value("only") == "only"

    def test_returns_first_among_multiple(self):
        assert _first_value("first", "second", "third") == "first"

    def test_zero_integer_skipped(self):
        assert _first_value(0, "fallback") == "fallback"

    def test_all_non_string_types(self):
        assert _first_value(1, 2.0, True, None, []) == ""

    def test_string_with_only_spaces_skipped(self):
        assert _first_value("   ", "real") == "real"

    def test_mixed_types_first_valid_string(self):
        assert _first_value(None, 42, "  ", "target", "other") == "target"


# ---------------------------------------------------------------------------
# resolve_model_name
# ---------------------------------------------------------------------------


class TestResolveModelName:
    """Tests for resolve_model_name — provider prefix resolution."""

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_slash_prefix_returns_unchanged(self, mock_settings):
        """Models with '/' already are returned as-is."""
        assert (
            resolve_model_name("nvidia_nim/llama-3.2-90b") == "nvidia_nim/llama-3.2-90b"
        )
        mock_settings.assert_not_called()

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_slash_prefix_openai(self, mock_settings):
        assert resolve_model_name("openai/gpt-4") == "openai/gpt-4"
        mock_settings.assert_not_called()

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_slash_prefix_gemini(self, mock_settings):
        assert (
            resolve_model_name("gemini/gemini-2.5-flash") == "gemini/gemini-2.5-flash"
        )
        mock_settings.assert_not_called()

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_model_gets_gemini_prefix(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("gemini-2.5-flash") == "gemini/gemini-2.5-flash"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_pro_model(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert (
                resolve_model_name("gemini-3-pro-preview")
                == "gemini/gemini-3-pro-preview"
            )

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_via_rag_api_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="sk-rag-key",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("gpt-4") == "openai/gpt-4"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_via_settings_openai_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="sk-openai",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("gpt-4o") == "openai/gpt-4o"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_via_env_rag_api_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {"RAG_API_KEY": "env-rag"}, clear=False):
            assert resolve_model_name("gpt-4") == "openai/gpt-4"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_via_env_openai_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env"}, clear=False):
            assert resolve_model_name("gpt-4o") == "openai/gpt-4o"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_via_rag_base_url(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="https://custom.api/v1",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("some-model") == "openai/some-model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_via_settings_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="nvapi-test",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("some-model") == "nvidia_nim/some-model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_via_env_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict(
            "os.environ", {"NVIDIA_BUILD_API_KEY": "nvapi-env"}, clear=False
        ):
            assert resolve_model_name("some-model") == "nvidia_nim/some-model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_default_gemini_when_no_keys(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("unknown-model") == "gemini/unknown-model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_takes_priority_over_nvidia(self, mock_settings):
        """OpenAI-compatible check runs before NVIDIA check."""
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="sk-key",
            openai_api_key="",
            nvidia_build_api_key="nvapi-key",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("model") == "openai/model"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_takes_priority_over_openai(self, mock_settings):
        """Gemini check runs before OpenAI-compatible check."""
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="sk-key",
            openai_api_key="",
            nvidia_build_api_key="",
        )
        with patch.dict("os.environ", {}, clear=False):
            assert resolve_model_name("gemini-2.5-pro") == "gemini/gemini-2.5-pro"


# ---------------------------------------------------------------------------
# get_client_params
# ---------------------------------------------------------------------------


class TestGetClientParams:
    """Tests for get_client_params — API key and base URL resolution."""

    # --- NVIDIA NIM ---

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_with_settings_key(self, mock_settings):
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
    def test_nvidia_nim_default_api_base(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="nvapi-test",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("nvidia_nim/llama-3.2")
        assert params["api_base"] == "https://integrate.api.nvidia.com/v1"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_custom_api_base(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="nvapi-test",
            rag_base_url="https://custom.nvidia.endpoint/v1",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("nvidia_nim/llama-3.2")
        assert params["api_base"] == "https://custom.nvidia.endpoint/v1"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_api_base_from_env(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="nvapi-test",
            rag_base_url="",
        )
        with patch.dict(
            "os.environ",
            {"NVIDIA_NIM_BASE_URL": "https://env.endpoint/v1"},
            clear=False,
        ):
            params = get_client_params("nvidia_nim/llama-3.2")
        assert params["api_base"] == "https://env.endpoint/v1"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_api_base_priority_rag_over_env(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="nvapi-test",
            rag_base_url="https://rag.endpoint/v1",
        )
        with patch.dict(
            "os.environ",
            {"NVIDIA_NIM_BASE_URL": "https://nvidia.endpoint/v1"},
            clear=False,
        ):
            params = get_client_params("nvidia_nim/llama-3.2")
        assert params["api_base"] == "https://rag.endpoint/v1"

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
    def test_nvidia_nim_key_from_env(self, mock_settings):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="",
            rag_base_url="",
        )
        with patch.dict(
            "os.environ", {"NVIDIA_BUILD_API_KEY": "nvapi-env"}, clear=False
        ):
            params = get_client_params("nvidia_nim/llama-3.2")
        assert params["api_key"] == "nvapi-env"

    # --- OpenAI ---

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_with_rag_api_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="sk-rag",
            openai_api_key="",
            rag_base_url="https://api.example.com/v1",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert params["model"] == "openai/gpt-4"
        assert params["api_key"] == "sk-rag"
        assert params["api_base"] == "https://api.example.com/v1"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_with_openai_api_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="",
            openai_api_key="sk-openai",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert params["api_key"] == "sk-openai"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_rag_key_priority_over_openai_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="sk-rag",
            openai_api_key="sk-openai",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert params["api_key"] == "sk-rag"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_no_base_url_excluded(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="sk-test",
            openai_api_key="",
            rag_base_url="",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert "api_base" not in params

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
    def test_openai_key_from_env_rag(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="",
            openai_api_key="",
            rag_base_url="",
        )
        with patch.dict("os.environ", {"RAG_API_KEY": "env-rag"}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert params["api_key"] == "env-rag"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_key_from_env_openai(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="",
            openai_api_key="",
            rag_base_url="",
        )
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-openai"}, clear=False):
            params = get_client_params("openai/gpt-4")
        assert params["api_key"] == "env-openai"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_base_url_from_env(self, mock_settings):
        mock_settings.return_value = MagicMock(
            rag_api_key="sk-test",
            openai_api_key="",
            rag_base_url="",
        )
        with patch.dict(
            "os.environ", {"RAG_BASE_URL": "https://env.api/v1"}, clear=False
        ):
            params = get_client_params("openai/gpt-4")
        assert params["api_base"] == "https://env.api/v1"

    # --- Gemini ---

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_with_extraction_api_key(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key-123",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("gemini/gemini-2.5-flash")
        assert params["model"] == "gemini/gemini-2.5-flash"
        assert params["api_key"] == "gemini-key-123"
        assert "api_base" not in params

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_via_env_var(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="",
        )
        with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
            params = get_client_params("gemini/gemini-2.5-flash")
        assert params["api_key"] == "env-key"

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_missing_key_raises(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="",
        )
        import os

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("GEMINI_API_KEY", "EXTRACTION_API_KEY")
        }
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(RuntimeError, match="No Gemini API key"):
                get_client_params("gemini/gemini-2.5-flash")

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_gemini_extraction_key_priority_over_env(self, mock_settings):
        mock_settings.return_value = MagicMock(
            extraction_api_key="settings-key",
        )
        with patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=False):
            params = get_client_params("gemini/gemini-2.5-flash")
        assert params["api_key"] == "settings-key"

    # --- Unprefixed models resolved to Gemini ---

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_unprefixed_gemini_model(self, mock_settings):
        """An unprefixed gemini-* model gets resolved to gemini/ prefix."""
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
            extraction_api_key="key",
        )
        with patch.dict("os.environ", {}, clear=False):
            params = get_client_params("gemini-2.5-flash")
        assert params["model"] == "gemini/gemini-2.5-flash"
        assert params["api_key"] == "key"


# ---------------------------------------------------------------------------
# create_completion
# ---------------------------------------------------------------------------


class TestCreateCompletion:
    """Tests for create_completion — the main LLM call entry point."""

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_basic_completion(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key",
        )
        mock_completion.return_value = MagicMock()

        messages = [{"role": "user", "content": "Hello"}]
        result = create_completion(model="gemini/gemini-2.5-flash", messages=messages)

        assert result == mock_completion.return_value
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gemini/gemini-2.5-flash"
        assert call_kwargs["messages"] == messages
        assert call_kwargs["temperature"] == 0
        assert call_kwargs["max_tokens"] == 4096

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_custom_temperature(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["temperature"] == 0.7

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_custom_max_tokens(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=2048,
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["max_tokens"] == 2048

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_extra_kwargs_passed_through(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
            top_p=0.9,
            stream=True,
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["top_p"] == 0.9
        assert call_kwargs["stream"] is True

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_api_key_included(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="gemini/gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["api_key"] == "gemini-key"

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_model_resolution_applied(self, mock_settings, mock_completion):
        """Unprefixed gemini- model gets resolved before calling completion."""
        mock_settings.return_value = MagicMock(
            rag_base_url="",
            rag_api_key="",
            openai_api_key="",
            nvidia_build_api_key="",
            extraction_api_key="gemini-key",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": "Hi"}],
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gemini/gemini-2.5-flash"

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_nvidia_nim_completion(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            nvidia_build_api_key="nvapi-test",
            rag_base_url="",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="nvidia_nim/llama-3.2",
            messages=[{"role": "user", "content": "Hi"}],
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "nvidia_nim/llama-3.2"
        assert call_kwargs["api_key"] == "nvapi-test"

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_missing_api_key_raises(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="",
        )
        import os

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("GEMINI_API_KEY", "EXTRACTION_API_KEY")
        }
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(RuntimeError, match="No Gemini API key"):
                create_completion(
                    model="gemini/gemini-2.5-flash",
                    messages=[{"role": "user", "content": "Hi"}],
                )
        mock_completion.assert_not_called()

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_completion_propagates_litellm_error(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            extraction_api_key="gemini-key",
        )
        mock_completion.side_effect = Exception("LiteLLM internal error")

        with pytest.raises(Exception, match="LiteLLM internal error"):
            create_completion(
                model="gemini/gemini-2.5-flash",
                messages=[{"role": "user", "content": "Hi"}],
            )

    @patch("lab_manager.services.litellm_client.completion")
    @patch("lab_manager.services.litellm_client.get_settings")
    def test_openai_completion_with_base_url(self, mock_settings, mock_completion):
        mock_settings.return_value = MagicMock(
            rag_api_key="sk-test",
            openai_api_key="",
            rag_base_url="https://custom.api/v1",
        )
        mock_completion.return_value = MagicMock()

        create_completion(
            model="openai/gpt-4",
            messages=[{"role": "user", "content": "Hi"}],
        )

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-4"
        assert call_kwargs["api_key"] == "sk-test"
        assert call_kwargs["api_base"] == "https://custom.api/v1"


# ---------------------------------------------------------------------------
# response_text
# ---------------------------------------------------------------------------


class TestResponseText:
    """Tests for response_text — extraction from LiteLLM responses."""

    def _make_response(self, content):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = content
        return resp

    def test_string_content_stripped(self):
        assert response_text(self._make_response("  Hello World  ")) == "Hello World"

    def test_empty_string_content(self):
        assert response_text(self._make_response("")) == ""

    def test_whitespace_only_string(self):
        assert response_text(self._make_response("   \n\t  ")) == ""

    def test_list_content_single_text_item(self):
        resp = self._make_response([{"type": "text", "text": "Hello"}])
        assert response_text(resp) == "Hello"

    def test_list_content_multiple_text_items(self):
        resp = self._make_response(
            [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ]
        )
        assert response_text(resp) == "Hello\nWorld"

    def test_list_content_with_non_text_type_items(self):
        resp = self._make_response(
            [
                {"type": "text", "text": "first"},
                {"type": "image", "text": "ignored-image"},
                {"type": "text", "text": "last"},
            ]
        )
        assert response_text(resp) == "first\nlast"

    def test_list_content_with_empty_text_items(self):
        resp = self._make_response(
            [
                {"type": "text", "text": "first"},
                {"type": "text", "text": ""},
                {"type": "text", "text": "last"},
            ]
        )
        assert response_text(resp) == "first\nlast"

    def test_list_content_with_object_items(self):
        text_part = MagicMock()
        text_part.text = "from_object"
        resp = self._make_response([text_part])
        assert response_text(resp) == "from_object"

    def test_list_content_mixed_dict_and_object(self):
        text_part = MagicMock()
        text_part.text = "from_object"
        resp = self._make_response(
            [
                {"type": "text", "text": "from_dict"},
                text_part,
            ]
        )
        assert response_text(resp) == "from_dict\nfrom_object"

    def test_list_content_empty_list(self):
        resp = self._make_response([])
        assert response_text(resp) == ""

    def test_list_content_all_empty_text(self):
        resp = self._make_response(
            [
                {"type": "text", "text": ""},
                {"type": "text", "text": ""},
            ]
        )
        assert response_text(resp) == ""

    def test_list_content_dict_without_text_key(self):
        resp = self._make_response([{"type": "text"}])
        assert response_text(resp) == ""

    def test_integer_content_fallback(self):
        assert response_text(self._make_response(42)) == "42"

    def test_float_content_fallback(self):
        assert response_text(self._make_response(3.14)) == "3.14"

    def test_none_content_fallback(self):
        assert response_text(self._make_response(None)) == "None"

    def test_list_content_item_with_no_type_key(self):
        resp = self._make_response([{"text": "no-type"}])
        assert response_text(resp) == ""

    def test_list_content_object_without_text_attr(self):
        obj = MagicMock(spec=[])
        resp = self._make_response([obj])
        assert response_text(resp) == ""

    def test_multiline_string_content(self):
        assert (
            response_text(self._make_response("line1\nline2\nline3"))
            == "line1\nline2\nline3"
        )


# ---------------------------------------------------------------------------
# load_litellm_config
# ---------------------------------------------------------------------------


class TestLoadLitellmConfig:
    """Tests for load_litellm_config — YAML config loading."""

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_load_valid_yaml(self, mock_settings):
        mock_settings.return_value = MagicMock(litellm_config_path="")
        yaml_content = "model_list:\n  - model_name: gemini-2.5-flash\n    litellm_params:\n      model: gemini/gemini-2.5-flash"
        with patch("builtins.open", mock_open(read_data=yaml_content)):
            result = load_litellm_config()
        assert result is not None
        assert "model_list" in result

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_file_not_found_returns_none(self, mock_settings):
        mock_settings.return_value = MagicMock(litellm_config_path="")
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = load_litellm_config()
        assert result is None

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_yaml_parse_error_returns_none(self, mock_settings):
        mock_settings.return_value = MagicMock(litellm_config_path="")
        with patch("builtins.open", mock_open(read_data=":invalid: yaml: [")):
            # yaml.safe_load may or may not raise depending on the content
            # Use a guaranteed exception
            pass
        with patch("builtins.open", mock_open(read_data="key: value")):
            with patch("yaml.safe_load", side_effect=Exception("parse error")):
                result = load_litellm_config()
        assert result is None

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_custom_config_path(self, mock_settings):
        mock_settings.return_value = MagicMock(
            litellm_config_path="/custom/path/config.yaml"
        )
        yaml_content = "test: true"
        with patch("builtins.open", mock_open(read_data=yaml_content)) as mocked_open:
            result = load_litellm_config()
        mocked_open.assert_called_once_with("/custom/path/config.yaml")
        assert result == {"test": True}

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_empty_config_path_uses_default(self, mock_settings):
        mock_settings.return_value = MagicMock(litellm_config_path="")
        yaml_content = "default: true"
        with patch("builtins.open", mock_open(read_data=yaml_content)) as mocked_open:
            result = load_litellm_config()
        mocked_open.assert_called_once_with("litellm_config.yaml")
        assert result == {"default": True}

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_empty_yaml_file(self, mock_settings):
        mock_settings.return_value = MagicMock(litellm_config_path="")
        with patch("builtins.open", mock_open(read_data="")):
            result = load_litellm_config()
        assert result is None  # yaml.safe_load("") returns None

    @patch("lab_manager.services.litellm_client.get_settings")
    def test_generic_exception_returns_none(self, mock_settings):
        mock_settings.return_value = MagicMock(litellm_config_path="")
        with patch("builtins.open", mock_open(read_data="key: value")):
            with patch("yaml.safe_load", side_effect=PermissionError("denied")):
                result = load_litellm_config()
        assert result is None
