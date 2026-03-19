"""Tests for the Meilisearch search service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.search import (
    _configure_index,
    _make_doc,
    get_search_client,
    search,
    search_all,
    suggest,
    sync_all,
    sync_documents,
    sync_inventory,
    sync_order_items,
    sync_orders,
    sync_products,
    sync_vendors,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    get_search_client.cache_clear()
    yield
    get_search_client.cache_clear()


class TestMakeDoc:
    def test_basic_fields(self):
        obj = MagicMock()
        obj.name = "Test"
        obj.id = 1
        result = _make_doc(obj, ["id", "name"])
        assert result == {"id": 1, "name": "Test"}

    def test_skips_none(self):
        obj = MagicMock()
        obj.name = "Test"
        obj.id = 1
        obj.missing = None
        result = _make_doc(obj, ["id", "name", "missing"])
        assert "missing" not in result


class TestConfigureIndex:
    def test_configures_all_attrs(self):
        mock_client = MagicMock()
        mock_idx = MagicMock()
        mock_client.index.return_value = mock_idx
        _configure_index(mock_client, "products")
        mock_idx.update_searchable_attributes.assert_called_once()
        mock_idx.update_filterable_attributes.assert_called_once()
        mock_idx.update_sortable_attributes.assert_called_once()

    def test_unknown_index(self):
        mock_client = MagicMock()
        mock_idx = MagicMock()
        mock_client.index.return_value = mock_idx
        _configure_index(mock_client, "nonexistent")
        mock_idx.update_searchable_attributes.assert_not_called()


class TestSyncFunctions:
    @patch("lab_manager.services.search.get_search_client")
    def test_sync_products(self, mock_get_client, db_session):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_products(db_session)
        assert count == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_vendors(self, mock_get_client, db_session):
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="Test Vendor", website="https://test.com", email="a@b.com")
        db_session.add(v)
        db_session.flush()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_vendors(db_session)
        assert count == 1
        mock_client.index.assert_called()

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_vendors_with_aliases(self, mock_get_client, db_session):
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="V", aliases=["a1", "a2"])
        db_session.add(v)
        db_session.flush()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_vendors(db_session)
        assert count == 1

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_orders(self, mock_get_client, db_session):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_orders(db_session)
        assert count == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_order_items(self, mock_get_client, db_session):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_order_items(db_session)
        assert count == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_documents(self, mock_get_client, db_session):
        from lab_manager.models.document import Document

        d = Document(
            file_path="/tmp/test.pdf",
            file_name="test.pdf",
            document_type="invoice",
            vendor_name="ACME",
            status="pending",
            ocr_text="test ocr text",
        )
        db_session.add(d)
        db_session.flush()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_documents(db_session)
        assert count == 1

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_inventory(self, mock_get_client, db_session):
        from datetime import date

        from lab_manager.models.inventory import InventoryItem
        from lab_manager.models.product import Product
        from lab_manager.models.vendor import Vendor

        v = Vendor(name="TestV")
        db_session.add(v)
        db_session.flush()
        p = Product(catalog_number="CAT1", name="Prod1", vendor_id=v.id)
        db_session.add(p)
        db_session.flush()

        item = InventoryItem(
            product_id=p.id,
            lot_number="LOT1",
            quantity_on_hand=10,
            unit="EA",
            expiry_date=date(2027, 1, 1),
            status="available",
            notes="test notes",
        )
        db_session.add(item)
        db_session.flush()

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count = sync_inventory(db_session)
        assert count == 1

    @patch("lab_manager.services.search.get_search_client")
    def test_sync_all(self, mock_get_client, db_session):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        # Make delete_all_documents raise for one index to exercise exception path
        mock_idx = MagicMock()
        mock_idx.delete_all_documents.side_effect = [Exception("not found")] + [
            None
        ] * 10
        mock_client.index.return_value = mock_idx
        counts = sync_all(db_session)
        assert isinstance(counts, dict)
        assert "products" in counts


class TestSearchFunctions:
    @patch("lab_manager.services.search.get_search_client")
    def test_search_single_index(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.index.return_value.search.return_value = {
            "hits": [{"id": 1, "name": "result"}]
        }
        result = search("test", index="products", limit=5)
        assert len(result) == 1
        assert result[0]["name"] == "result"

    @patch("lab_manager.services.search.get_search_client")
    def test_search_all(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_idx = MagicMock()
        mock_idx.search.return_value = {"hits": [{"id": 1}]}
        mock_client.index.return_value = mock_idx
        result = search_all("test", limit=5)
        assert isinstance(result, dict)

    @patch("lab_manager.services.search.get_search_client")
    def test_search_all_with_exception(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.index.return_value.search.side_effect = Exception("unavailable")
        result = search_all("test")
        assert result == {}

    @patch("lab_manager.services.search.get_search_client")
    def test_suggest(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        def mock_search(query, opts):
            return {"hits": [{"id": 1, "name": "Product X", "catalog_number": "CAT1"}]}

        mock_client.index.return_value.search.side_effect = mock_search
        result = suggest("prod", limit=10)
        assert isinstance(result, list)
        assert len(result) > 0

    @patch("lab_manager.services.search.get_search_client")
    def test_suggest_with_exceptions(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.index.return_value.search.side_effect = Exception("fail")
        result = suggest("test", limit=5)
        assert result == []
