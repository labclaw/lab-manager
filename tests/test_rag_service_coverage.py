"""Tests for services/rag.py — cover _generate_sql, _fallback_search, ask."""

from unittest.mock import MagicMock, patch

from lab_manager.services.rag import MAX_QUESTION_LENGTH, _serialize_rows

SEARCH_PATCH = "lab_manager.services.search.search"


class TestSerializeRows:
    def test_decimals_converted(self):
        from decimal import Decimal

        rows = [{"price": Decimal("10.50")}]
        result = _serialize_rows(rows)
        assert result[0]["price"] == 10.50

    def test_datetime_converted(self):
        from datetime import datetime

        dt = datetime(2026, 3, 23, 12, 0)
        rows = [{"created": dt}]
        result = _serialize_rows(rows)
        assert result[0]["created"] == "2026-03-23T12:00:00"


class TestGenerateSql:
    def test_plain_sql(self):
        from lab_manager.services.rag import _generate_sql

        with patch(
            "lab_manager.services.rag._generate_completion",
            return_value="SELECT * FROM vendors",
        ):
            sql = _generate_sql("list all vendors")
            assert sql == "SELECT * FROM vendors"

    def test_markdown_fence_stripped(self):
        from lab_manager.services.rag import _generate_sql

        with patch(
            "lab_manager.services.rag._generate_completion",
            return_value="```sql\nSELECT * FROM vendors LIMIT 10\n```",
        ):
            sql = _generate_sql("list vendors")
            assert sql == "SELECT * FROM vendors LIMIT 10"


class TestGenerateCompletion:
    def test_uses_centralized_litellm_client(self):
        from lab_manager.services.rag import _generate_completion

        mock_response = MagicMock()

        with (
            patch(
                "lab_manager.services.rag.get_settings",
                return_value=MagicMock(rag_model="rag-primary"),
            ),
            patch(
                "lab_manager.services.rag.create_completion",
                return_value=mock_response,
            ) as mock_create,
            patch(
                "lab_manager.services.rag.response_text",
                return_value="final answer",
            ) as mock_text,
        ):
            result = _generate_completion("prompt text")

        assert result == "final answer"
        mock_create.assert_called_once_with(
            model="rag-primary",
            messages=[{"role": "user", "content": "prompt text"}],
            temperature=0,
        )
        mock_text.assert_called_once_with(mock_response)


class TestFallbackSearch:
    def test_fallback_returns_message(self):
        from lab_manager.services.rag import _fallback_search

        with patch(SEARCH_PATCH, return_value=[]):
            result = _fallback_search("query")
            assert result["answer"] == "No results found via text search either."


class TestAsk:
    def setup_method(self):
        """Clear RAG response cache before each test."""
        from lab_manager.services.rag import _CACHE

        _CACHE.clear()

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
                "lab_manager.services.rag._generate_sql", return_value="SELECT 1"
            ) as mock_sql,
            patch("lab_manager.services.rag._execute_sql", return_value=[]),
            patch("lab_manager.services.rag._format_answer", return_value="answer"),
        ):
            mock_session = MagicMock()
            ask(long_q, mock_session)
            mock_sql.assert_called_once()
            called_question = mock_sql.call_args[0][0]
            assert len(called_question) == MAX_QUESTION_LENGTH

    def test_sql_gen_fails_falls_back(self):
        from lab_manager.services.rag import ask

        with (
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
            patch("lab_manager.services.rag._generate_sql", return_value="SELECT 1"),
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=[{"n": 1, "name": "Sigma"}],
            ),
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
                "lab_manager.services.rag._generate_sql",
                return_value="SELECT * FROM vendors",
            ),
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=[{"name": "Sigma", "id": 1}],
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
