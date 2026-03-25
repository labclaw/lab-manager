"""Tests for RAG query planning step."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.rag import (
    _ALLOWED_TABLES,
    _CACHE,
    _generate_plan,
    _parse_plan,
    _validate_plan,
)


class TestParsePlan:
    def test_parses_well_formed_plan(self):
        raw = (
            "TABLES: vendors, orders\n"
            "JOINS: orders.vendor_id = vendors.id\n"
            "FILTERS: order_date > 2026-01-01\n"
            "AGGREGATION: COUNT grouped by vendor\n"
            "RESULT: list of vendor names with order counts"
        )
        plan = _parse_plan(raw)
        assert plan["tables"] == ["vendors", "orders"]
        assert "vendor_id" in plan["joins"]
        assert "order_date" in plan["filters"]
        assert "COUNT" in plan["aggregation"]
        assert "vendor names" in plan["result"]

    def test_parses_none_values(self):
        raw = (
            "TABLES: products\n"
            "JOINS: none\n"
            "FILTERS: none\n"
            "AGGREGATION: none\n"
            "RESULT: single count"
        )
        plan = _parse_plan(raw)
        assert plan["tables"] == ["products"]
        assert plan["joins"] == "none"

    def test_handles_extra_whitespace(self):
        raw = "  TABLES:  vendors ,  products  \nJOINS: none\n"
        plan = _parse_plan(raw)
        assert "vendors" in plan["tables"]
        assert "products" in plan["tables"]

    def test_preserves_raw(self):
        raw = "TABLES: vendors\nRESULT: all vendors"
        plan = _parse_plan(raw)
        assert plan["raw"] == raw

    def test_empty_input(self):
        plan = _parse_plan("")
        assert plan["tables"] == []


class TestValidatePlan:
    def test_valid_plan(self):
        plan = {"tables": ["vendors", "orders"]}
        issues = _validate_plan(plan)
        assert issues == []

    def test_no_tables(self):
        plan = {"tables": []}
        issues = _validate_plan(plan)
        assert any("no tables" in i for i in issues)

    def test_disallowed_table(self):
        plan = {"tables": ["vendors", "secret_table"]}
        issues = _validate_plan(plan)
        assert any("disallowed" in i for i in issues)

    def test_all_allowed_tables(self):
        for table in _ALLOWED_TABLES:
            plan = {"tables": [table]}
            assert _validate_plan(plan) == []


class TestGeneratePlan:
    def test_generates_plan_from_llm(self):
        mock_response = (
            "TABLES: vendors\n"
            "JOINS: none\n"
            "FILTERS: none\n"
            "AGGREGATION: COUNT\n"
            "RESULT: single count of vendors"
        )
        with patch(
            "lab_manager.services.rag._generate_completion",
            return_value=mock_response,
        ):
            plan = _generate_plan("how many vendors")
        assert plan["tables"] == ["vendors"]
        assert "COUNT" in plan["aggregation"]

    def test_plan_failure_raises(self):
        with patch(
            "lab_manager.services.rag._generate_completion",
            side_effect=RuntimeError("API error"),
        ):
            with pytest.raises(RuntimeError):
                _generate_plan("test question")


class TestAskWithPlanning:
    """Integration tests for the ask() function with query planning."""

    def setup_method(self):
        _CACHE.clear()

    def test_ask_uses_plan_in_sql_generation(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._generate_plan",
                return_value={
                    "tables": ["vendors"],
                    "joins": "none",
                    "filters": "none",
                    "aggregation": "COUNT",
                    "result": "single count",
                },
            ),
            patch("lab_manager.services.rag._validate_plan", return_value=[]),
            patch(
                "lab_manager.services.rag._generate_sql",
                return_value="SELECT COUNT(*) FROM vendors",
            ) as mock_sql,
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=[{"count": 5}],
            ),
        ):
            result = ask("how many vendors", MagicMock())

        # _generate_sql should receive the plan
        assert mock_sql.call_args[1]["plan"] is not None
        assert result["source"] == "sql"
        assert "query_plan" in result

    def test_ask_proceeds_without_plan_on_failure(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._generate_plan",
                side_effect=RuntimeError("plan failed"),
            ),
            patch(
                "lab_manager.services.rag._generate_sql",
                return_value="SELECT COUNT(*) FROM vendors",
            ) as mock_sql,
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=[{"count": 5}],
            ),
        ):
            result = ask("how many vendors", MagicMock())

        # Should still work, just without a plan
        mock_sql.assert_called_once()
        assert mock_sql.call_args[1]["plan"] is None
        assert result["source"] == "sql"
        assert "query_plan" not in result

    def test_ask_skips_invalid_plan(self):
        from lab_manager.services.rag import ask

        with (
            patch(
                "lab_manager.services.rag._generate_plan",
                return_value={"tables": ["evil_table"]},
            ),
            patch(
                "lab_manager.services.rag._validate_plan",
                return_value=["Plan references disallowed table: evil_table"],
            ),
            patch(
                "lab_manager.services.rag._generate_sql",
                return_value="SELECT * FROM vendors",
            ) as mock_sql,
            patch(
                "lab_manager.services.rag._execute_sql",
                return_value=[{"name": "Sigma"}],
            ),
            patch(
                "lab_manager.services.rag._format_answer",
                return_value="Found vendors.",
            ),
        ):
            result = ask("list vendors", MagicMock())

        # Plan was invalid, so SQL gen should get plan=None
        assert mock_sql.call_args[1]["plan"] is None


class TestGenerateSqlWithPlan:
    def test_sql_generation_includes_plan_context(self):
        from lab_manager.services.rag import _generate_sql

        plan = {
            "tables": ["vendors", "orders"],
            "joins": "orders.vendor_id = vendors.id",
            "filters": "order_date this month",
            "aggregation": "COUNT per vendor",
            "result": "vendor names with counts",
        }
        with patch(
            "lab_manager.services.rag._generate_completion",
            return_value="SELECT v.name, COUNT(*) FROM vendors v JOIN orders o ON o.vendor_id = v.id GROUP BY v.name",
        ) as mock_completion:
            sql = _generate_sql("orders per vendor this month", plan=plan)

        prompt = mock_completion.call_args[0][0]
        assert "QUERY PLAN" in prompt
        assert "vendors, orders" in prompt

    def test_sql_generation_without_plan(self):
        from lab_manager.services.rag import _generate_sql

        with patch(
            "lab_manager.services.rag._generate_completion",
            return_value="SELECT * FROM vendors",
        ) as mock_completion:
            sql = _generate_sql("list vendors", plan=None)

        prompt = mock_completion.call_args[0][0]
        assert "QUERY PLAN" not in prompt
