"""Tests for the MCP server tool registration and responses."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


from lab_manager.mcp.server import (
    _format_json,
    ask_lab,
    get_analytics,
    get_inventory_status,
    mcp,
    search_documents,
    search_inventory,
)


class TestMCPServerRegistration:
    """Verify that the MCP server has the expected tools registered."""

    def test_server_name(self):
        assert mcp.name == "Lab Manager"

    def test_tools_registered(self):
        """All five tools should be registered on the FastMCP instance."""
        tool_names = {name for name in mcp._tool_manager._tools}
        expected = {
            "search_inventory",
            "get_inventory_status",
            "search_documents",
            "get_analytics",
            "ask_lab",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    def test_tool_count(self):
        """Should have exactly 5 tools."""
        assert len(mcp._tool_manager._tools) == 5


class TestFormatJson:
    def test_basic_dict(self):
        result = _format_json({"a": 1, "b": "hello"})
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": "hello"}

    def test_handles_non_serializable(self):
        from datetime import date

        result = _format_json({"date": date(2026, 3, 25)})
        assert "2026-03-25" in result


class TestSearchInventory:
    """Test search_inventory tool with mocked HTTP."""

    @patch("lab_manager.mcp.server._client")
    def test_search_all_indexes(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": "ethanol",
            "results": {
                "products": [{"id": 1, "name": "Ethanol 200 proof"}],
            },
            "total": 1,
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = search_inventory("ethanol")
        assert "1 total results" in result
        assert "Ethanol 200 proof" in result

    @patch("lab_manager.mcp.server._client")
    def test_search_specific_index(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": "sigma",
            "index": "vendors",
            "hits": [{"id": 1, "name": "Sigma-Aldrich"}],
            "count": 1,
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = search_inventory("sigma", index="vendors")
        assert "1 results" in result
        assert "Sigma-Aldrich" in result

    @patch("lab_manager.mcp.server._client")
    def test_search_no_results(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"query": "xyz", "results": {}, "total": 0}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = search_inventory("xyz")
        assert "No results" in result


class TestGetInventoryStatus:
    @patch("lab_manager.mcp.server._client")
    def test_returns_formatted_status(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "total_products": 150,
            "total_vendors": 30,
            "total_orders": 200,
            "total_inventory_items": 500,
            "total_documents": 279,
            "total_staff": 5,
            "documents_pending_review": 10,
            "documents_approved": 250,
            "orders_by_status": {"received": 180, "pending": 20},
            "inventory_by_status": {"available": 400, "consumed": 100},
            "expiring_soon": [
                {
                    "product_name": "Trypsin",
                    "lot_number": "LOT-001",
                    "quantity_on_hand": 5,
                    "expiry_date": "2026-04-15",
                }
            ],
            "low_stock_count": 3,
            "recent_orders": [],
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = get_inventory_status()
        assert "Products: 150" in result
        assert "Low stock products: 3" in result
        assert "Trypsin" in result
        assert "LOT-001" in result
        assert "received: 180" in result


class TestSearchDocuments:
    @patch("lab_manager.mcp.server._client")
    def test_search_found(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hits": [
                {
                    "file_name": "invoice_sigma_2026.pdf",
                    "document_type": "invoice",
                    "vendor_name": "Sigma-Aldrich",
                    "status": "approved",
                }
            ],
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = search_documents("sigma invoice")
        assert "invoice_sigma_2026.pdf" in result
        assert "Sigma-Aldrich" in result

    @patch("lab_manager.mcp.server._client")
    def test_search_empty(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"hits": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = search_documents("nonexistent")
        assert "No documents found" in result


class TestAskLab:
    @patch("lab_manager.mcp.server._client")
    def test_ask_returns_answer(self, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "question": "How many products?",
            "answer": "There are 150 products in the database.",
            "source": "sql",
            "row_count": 1,
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = ask_lab("How many products?")
        assert "150 products" in result
        assert "sql" in result


class TestGetAnalytics:
    @patch("lab_manager.mcp.server._client")
    def test_analytics_summary(self, mock_client_fn):
        # Mock multiple endpoint responses
        dashboard_resp = MagicMock()
        dashboard_resp.json.return_value = {
            "total_products": 100,
            "total_vendors": 20,
            "total_orders": 150,
            "low_stock_count": 2,
        }
        dashboard_resp.raise_for_status = MagicMock()

        spending_resp = MagicMock()
        spending_resp.json.return_value = [
            {"vendor_name": "Sigma", "total_spend": 50000.0, "order_count": 30}
        ]
        spending_resp.raise_for_status = MagicMock()

        value_resp = MagicMock()
        value_resp.json.return_value = {"total_value": 125000.50, "item_count": 500}
        value_resp.raise_for_status = MagicMock()

        top_resp = MagicMock()
        top_resp.json.return_value = [
            {
                "catalog_number": "E7023",
                "name": "Ethanol",
                "vendor": "Sigma",
                "times_ordered": 15,
            }
        ]
        top_resp.raise_for_status = MagicMock()

        monthly_resp = MagicMock()
        monthly_resp.json.return_value = [
            {"month": "2026-03", "total_spend": 12000.0, "order_count": 8}
        ]
        monthly_resp.raise_for_status = MagicMock()

        # Return different responses for different URLs
        def side_effect(url, **kwargs):
            if "dashboard" in url:
                return dashboard_resp
            if "spending-by-vendor" in url:
                return spending_resp
            if "inventory-value" in url:
                return value_resp
            if "top-products" in url:
                return top_resp
            if "spending-by-month" in url:
                return monthly_resp
            return MagicMock()

        mock_client = MagicMock()
        mock_client.get.side_effect = side_effect
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_fn.return_value = mock_client

        result = get_analytics()
        assert "Total products: 100" in result
        assert "$125,000.50" in result
        assert "Sigma" in result
        assert "Ethanol" in result
        assert "2026-03" in result
