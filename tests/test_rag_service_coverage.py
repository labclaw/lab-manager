"""Tests for services/rag.py — cover _resolved_rag_model, _get_client, _response_text, _generate_sql, _fallback_search, ask."""

from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.rag import (
    MAX_QUESTION_LENGTH,
    _first_value,
    _has_value,
    _serialize_rows,
)

SEARCH_PATCH = "lab_manager.services.search.search"


class TestHasValue:
    def test_nonempty_string(self):
        assert _has_value("hello") is True

    def test_empty_string(self):
        assert _has_value("") is False

    def test_whitespace_string(self):
        assert _has_value("   ") is False

    def test_none(self):
        assert _has_value(None) is False

    def test_integer(self):
        assert _has_value(42) is False


class TestFirstValue:
    def test_first_nonempty(self):
        assert _first_value("", "hello", "world") == "hello"

    def test_none_values(self):
        assert _first_value(None, None, "found") == "found"

    def test_all_empty(self):
        assert _first_value("", "  ", None) == ""

    def test_strips(self):
        assert _first_value("  hello  ") == "hello"


class TestResolvedRagModel:
    def test_full_path_passthrough(self):
        with patch("lab_manager.services.rag.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_model="openai/gpt-4",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict("os.environ", {}, clear=False):
                from lab_manager.services.rag import _resolved_rag_model

                assert _resolved_rag_model() == "openai/gpt-4"

    def test_gemini_prefix(self):
        with patch("lab_manager.services.rag.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_model="gemini-2.5-flash",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}, clear=False):
                from lab_manager.services.rag import _resolved_rag_model

                assert _resolved_rag_model() == "gemini/gemini-2.5-flash"

    def test_openai_with_key(self):
        with patch("lab_manager.services.rag.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_model="gpt-4",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="sk-test",
                nvidia_build_api_key="",
            )
            with patch.dict("os.environ", {}, clear=False):
                from lab_manager.services.rag import _resolved_rag_model

                assert _resolved_rag_model() == "openai/gpt-4"

    def test_nvidia_with_key(self):
        with patch("lab_manager.services.rag.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_model="llama-3.2-90b",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="nv-key",
            )
            with patch.dict("os.environ", {}, clear=False):
                from lab_manager.services.rag import _resolved_rag_model

                assert _resolved_rag_model() == "nvidia_nim/llama-3.2-90b"

    def test_nvidia_from_env(self):
        with patch("lab_manager.services.rag.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rag_model="llama-3.2-90b",
                rag_base_url="",
                rag_api_key="",
                openai_api_key="",
                nvidia_build_api_key="",
            )
            with patch.dict(
                "os.environ", {"NVIDIA_BUILD_API_KEY": "nv-env"}, clear=False
            ):
                from lab_manager.services.rag import _resolved_rag_model

                assert _resolved_rag_model() == "nvidia_nim/llama-3.2-90b"


class TestGetClient:
    def test_nvidia_client(self):
        with (
            patch(
                "lab_manager.services.rag._resolved_rag_model",
                return_value="nvidia_nim/llama",
            ),
            patch("lab_manager.services.rag.get_settings") as mock_settings,
            patch.dict("os.environ", {}, clear=False),
        ):
            mock_settings.return_value = MagicMock(
                nvidia_build_api_key="nv-key", rag_base_url=""
            )
            from lab_manager.services.rag import _get_client

            _get_client.cache_clear()
            result = _get_client()
            assert result["model"] == "nvidia_nim/llama"
            assert result["api_key"] == "nv-key"
            _get_client.cache_clear()

    def test_nvidia_no_key_raises(self):
        with (
            patch(
                "lab_manager.services.rag._resolved_rag_model",
                return_value="nvidia_nim/llama",
            ),
            patch("lab_manager.services.rag.get_settings") as mock_settings,
            patch.dict("os.environ", {}, clear=False),
        ):
            mock_settings.return_value = MagicMock(
                nvidia_build_api_key="", rag_base_url=""
            )
            from lab_manager.services.rag import _get_client

            _get_client.cache_clear()
            with pytest.raises(RuntimeError, match="NVIDIA Build API key"):
                _get_client()
            _get_client.cache_clear()

    def test_openai_client(self):
        with (
            patch(
                "lab_manager.services.rag._resolved_rag_model",
                return_value="openai/gpt-4",
            ),
            patch("lab_manager.services.rag.get_settings") as mock_settings,
            patch.dict("os.environ", {}, clear=False),
        ):
            mock_settings.return_value = MagicMock(
                rag_api_key="",
                openai_api_key="sk-test",
                rag_base_url="https://api.openai.com/v1",
            )
            from lab_manager.services.rag import _get_client

            _get_client.cache_clear()
            result = _get_client()
            assert result["model"] == "openai/gpt-4"
            assert result["api_key"] == "sk-test"
            assert result["api_base"] == "https://api.openai.com/v1"
            _get_client.cache_clear()

    def test_openai_no_key_raises(self):
        with (
            patch(
                "lab_manager.services.rag._resolved_rag_model",
                return_value="openai/gpt-4",
            ),
            patch("lab_manager.services.rag.get_settings") as mock_settings,
            patch.dict("os.environ", {}, clear=False),
        ):
            mock_settings.return_value = MagicMock(
                rag_api_key="", openai_api_key="", rag_base_url=""
            )
            from lab_manager.services.rag import _get_client

            _get_client.cache_clear()
            with pytest.raises(RuntimeError, match="RAG API key"):
                _get_client()
            _get_client.cache_clear()

    def test_gemini_client(self):
        with (
            patch(
                "lab_manager.services.rag._resolved_rag_model",
                return_value="gemini/gemini-2.5-flash",
            ),
            patch("lab_manager.services.rag.get_settings") as mock_settings,
            patch.dict("os.environ", {"GEMINI_API_KEY": "g-key"}, clear=False),
        ):
            mock_settings.return_value = MagicMock(extraction_api_key="")
            from lab_manager.services.rag import _get_client

            _get_client.cache_clear()
            result = _get_client()
            assert result["model"] == "gemini/gemini-2.5-flash"
            assert result["api_key"] == "g-key"
            _get_client.cache_clear()

    def test_gemini_no_key_raises(self):
        with (
            patch(
                "lab_manager.services.rag._resolved_rag_model",
                return_value="gemini/gemini-2.5-flash",
            ),
            patch("lab_manager.services.rag.get_settings") as mock_settings,
            patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False),
        ):
            mock_settings.return_value = MagicMock(extraction_api_key="")
            from lab_manager.services.rag import _get_client

            _get_client.cache_clear()
            with pytest.raises(RuntimeError, match="Gemini API key"):
                _get_client()
            _get_client.cache_clear()


class TestResponseText:
    def test_string_content(self):
        from lab_manager.services.rag import _response_text

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "  answer text  "
        assert _response_text(resp) == "answer text"

    def test_list_content_dict(self):
        from lab_manager.services.rag import _response_text

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = [
            {"type": "text", "text": "part1"},
            {"type": "image", "url": "..."},
            {"type": "text", "text": "part2"},
        ]
        assert _response_text(resp) == "part1\npart2"

    def test_list_content_object(self):
        from lab_manager.services.rag import _response_text

        text_part = MagicMock()
        text_part.text = "object text"
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = [text_part]
        assert _response_text(resp) == "object text"

    def test_non_string_content(self):
        from lab_manager.services.rag import _response_text

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = 42
        assert _response_text(resp) == "42"

    def test_list_empty_parts(self):
        from lab_manager.services.rag import _response_text

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = [{"type": "image"}]
        assert _response_text(resp) == ""


class TestGenerateSql:
    def test_plain_sql(self):
        from lab_manager.services.rag import _generate_sql

        mock_client = {"model": "test"}
        with patch(
            "lab_manager.services.rag._generate_completion",
            return_value="SELECT * FROM vendors",
        ):
            sql = _generate_sql(mock_client, "list all vendors")
            assert sql == "SELECT * FROM vendors"

    def test_markdown_fence_stripped(self):
        from lab_manager.services.rag import _generate_sql

        mock_client = {"model": "test"}
        fenced = "```sql\nSELECT * FROM vendors LIMIT 10\n```"
        with patch(
            "lab_manager.services.rag._generate_completion", return_value=fenced
        ):
            sql = _generate_sql(mock_client, "list vendors")
            assert sql == "SELECT * FROM vendors LIMIT 10"


class TestSerializeRows:
    def test_basic(self):
        rows = [{"a": 1, "b": "hello"}, {"a": 2}]
        result = _serialize_rows(rows)
        assert len(result) == 2
        assert result[0]["a"] == 1

    def test_empty(self):
        assert _serialize_rows([]) == []


class TestFallbackSearch:
    def test_search_with_hits(self):
        from lab_manager.services.rag import _fallback_search

        with patch(SEARCH_PATCH, return_value=[{"id": 1, "name": "test"}]):
            result = _fallback_search("test query")
            assert result["source"] == "search"
            assert result["answer"] == "Found 1 results via text search."

    def test_search_no_hits(self):
        from lab_manager.services.rag import _fallback_search

        with patch(SEARCH_PATCH, return_value=[]):
            result = _fallback_search("nothing")
            assert result["answer"] == "No results found via text search either."

    def test_search_exception(self):
        from lab_manager.services.rag import _fallback_search

        with patch(SEARCH_PATCH, side_effect=Exception("meili down")):
            result = _fallback_search("query")
            assert result["answer"] == "Search is currently unavailable."


class TestAsk:
    def test_empty_question(self):
        from lab_manager.services.rag import ask

        with patch("lab_manager.services.rag.Session") as mock_session:
            result = ask("", mock_session)
            assert result["answer"] == "Please provide a question."

    def test_whitespace_question(self):
        from lab_manager.services.rag import ask

        with patch("lab_manager.services.rag.Session") as mock_session:
            result = ask("   ", mock_session)
            assert result["answer"] == "Please provide a question."

    def test_long_question_truncated(self):
        from lab_manager.services.rag import ask

        long_q = "A" * (MAX_QUESTION_LENGTH + 100)
        with (
            patch(
                "lab_manager.services.rag._get_client", return_value={"model": "test"}
            ),
            patch(
                "lab_manager.services.rag._generate_sql", return_value="SELECT 1"
            ) as mock_sql,
            patch("lab_manager.services.rag._execute_sql", return_value=[]),
            patch("lab_manager.services.rag._format_answer", return_value="answer"),
        ):
            mock_session = MagicMock()
            result = ask(long_q, mock_session)
            mock_sql.assert_called_once()
            called_question = mock_sql.call_args[0][1]
            assert len(called_question) == MAX_QUESTION_LENGTH

    def test_client_init_falls_back_to_search(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._get_client",
                side_effect=RuntimeError("no key"),
            ),
            patch(
                "lab_manager.services.rag._fallback_search",
                return_value={"answer": "fallback"},
            ) as mock_fb,
        ):
            result = ask("test", MagicMock())
            assert result["answer"] == "fallback"
            mock_fb.assert_called_once()

    def test_sql_gen_fails_falls_back(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._get_client", return_value={"model": "test"}
            ),
            patch(
                "lab_manager.services.rag._generate_sql",
                side_effect=Exception("gen fail"),
            ),
            patch(
                "lab_manager.services.rag._fallback_search",
                return_value={"answer": "fallback"},
            ),
        ):
            result = ask("test", MagicMock())
            assert result["answer"] == "fallback"

    def test_sql_exec_fails_falls_back(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._get_client", return_value={"model": "test"}
            ),
            patch("lab_manager.services.rag._generate_sql", return_value="SELECT 1"),
            patch(
                "lab_manager.services.rag._execute_sql",
                side_effect=Exception("exec fail"),
            ),
            patch(
                "lab_manager.services.rag._fallback_search",
                return_value={"answer": "fallback"},
            ),
        ):
            result = ask("test", MagicMock())
            assert result["answer"] == "fallback"

    def test_format_fails_gracefully(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._get_client", return_value={"model": "test"}
            ),
            patch("lab_manager.services.rag._generate_sql", return_value="SELECT 1"),
            patch("lab_manager.services.rag._execute_sql", return_value=[{"n": 1}]),
            patch(
                "lab_manager.services.rag._format_answer",
                side_effect=Exception("fmt fail"),
            ),
        ):
            result = ask("test", MagicMock())
            assert "formatting failed" in result["answer"]

    def test_happy_path(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._get_client", return_value={"model": "test"}
            ),
            patch(
                "lab_manager.services.rag._generate_sql",
                return_value="SELECT * FROM vendors",
            ),
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=[{"name": "Sigma"}],
            ),
            patch(
                "lab_manager.services.rag._format_answer",
                return_value="There is 1 vendor.",
            ),
        ):
            result = ask("how many vendors", MagicMock())
            assert result["source"] == "sql"
            assert result["answer"] == "There is 1 vendor."
            assert result["sql"] == "SELECT * FROM vendors"
            assert result["row_count"] == 1
