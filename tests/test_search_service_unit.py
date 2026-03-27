"""Comprehensive unit tests for the Meilisearch search service.

Covers:
- _make_doc helper
- _configure_index helper
- Individual record indexing (product, vendor, order, order_item, document, inventory)
- Sync functions (batch indexing with DB session)
- search / search_all / suggest query functions
- sync_all full reindex
- Error handling (Meilisearch unavailable, connection failures)
- Data serialization edge cases (dates, decimals, None, empty strings)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.services.search import (
    INDEX_CONFIG,
    _BATCH_SIZE,
    _configure_index,
    _make_doc,
    _safe_index,
    get_search_client,
    index_document_record,
    index_inventory_record,
    index_order_item_record,
    index_order_record,
    index_product_record,
    index_vendor_record,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear lru_cache on get_search_client between tests."""
    get_search_client.cache_clear()
    yield
    get_search_client.cache_clear()


def _mock_client():
    """Return a fresh MagicMock that pretends to be a meilisearch.Client."""
    client = MagicMock()
    idx = MagicMock()
    client.index.return_value = idx
    return client, idx


# ---------------------------------------------------------------------------
# TestMakeDoc
# ---------------------------------------------------------------------------


class TestMakeDoc:
    """Tests for the _make_doc helper function."""

    def test_basic_fields(self):
        obj = MagicMock()
        obj.name = "Test"
        obj.id = 1
        result = _make_doc(obj, ["id", "name"])
        assert result == {"id": 1, "name": "Test"}

    def test_skips_none_values(self):
        obj = MagicMock()
        obj.name = "Test"
        obj.id = 1
        obj.missing = None
        result = _make_doc(obj, ["id", "name", "missing"])
        assert "missing" not in result
        assert result == {"id": 1, "name": "Test"}

    def test_serializes_date(self):
        obj = MagicMock()
        obj.id = 1
        obj.order_date = date(2026, 3, 27)
        result = _make_doc(obj, ["id", "order_date"])
        assert result["order_date"] == "2026-03-27"

    def test_serializes_datetime(self):
        obj = MagicMock()
        obj.id = 1
        obj.created_at = datetime(2026, 3, 27, 14, 30, 0)
        result = _make_doc(obj, ["id", "created_at"])
        assert result["created_at"] == "2026-03-27T14:30:00"

    def test_serializes_decimal(self):
        obj = MagicMock()
        obj.id = 1
        obj.unit_price = Decimal("19.99")
        result = _make_doc(obj, ["id", "unit_price"])
        assert result["unit_price"] == "19.99"

    def test_preserves_int_float_str(self):
        obj = MagicMock()
        obj.id = 1
        obj.count = 42
        obj.weight = 3.14
        obj.label = "hello"
        result = _make_doc(obj, ["id", "count", "weight", "label"])
        assert result["count"] == 42
        assert result["weight"] == 3.14
        assert result["label"] == "hello"

    def test_preserves_list_and_dict(self):
        obj = MagicMock()
        obj.id = 1
        obj.tags = ["a", "b"]
        obj.meta = {"k": "v"}
        result = _make_doc(obj, ["id", "tags", "meta"])
        assert result["tags"] == ["a", "b"]
        assert result["meta"] == {"k": "v"}

    def test_empty_fields_list(self):
        obj = MagicMock()
        result = _make_doc(obj, [])
        assert result == {}

    def test_missing_attribute_returns_none(self):
        """If getattr returns None for a missing attribute, it is skipped."""

        class Obj:
            id = 5

        result = _make_doc(Obj(), ["id", "nonexistent"])
        assert result == {"id": 5}

    def test_all_none_fields(self):
        obj = MagicMock(spec=[])
        obj.id = None
        obj.name = None
        result = _make_doc(obj, ["id", "name"])
        assert result == {}


# ---------------------------------------------------------------------------
# TestConfigureIndex
# ---------------------------------------------------------------------------


class TestConfigureIndex:
    """Tests for _configure_index."""

    def test_products_index_configures_all_attrs(self):
        client, idx = _mock_client()
        _configure_index(client, "products")
        idx.update_searchable_attributes.assert_called_once_with(
            INDEX_CONFIG["products"]["searchableAttributes"]
        )
        idx.update_filterable_attributes.assert_called_once_with(
            INDEX_CONFIG["products"]["filterableAttributes"]
        )
        idx.update_sortable_attributes.assert_called_once_with(
            INDEX_CONFIG["products"]["sortableAttributes"]
        )

    def test_vendors_index(self):
        client, idx = _mock_client()
        _configure_index(client, "vendors")
        idx.update_searchable_attributes.assert_called_once()
        # vendors have empty filterableAttributes
        idx.update_filterable_attributes.assert_called_once_with([])
        idx.update_sortable_attributes.assert_called_once()

    def test_unknown_index_no_calls(self):
        client, idx = _mock_client()
        _configure_index(client, "nonexistent")
        idx.update_searchable_attributes.assert_not_called()
        idx.update_filterable_attributes.assert_not_called()
        idx.update_sortable_attributes.assert_not_called()

    @pytest.mark.parametrize(
        "index_name",
        list(INDEX_CONFIG.keys()),
    )
    def test_all_known_indexes_apply_config(self, index_name):
        """Every index in INDEX_CONFIG should trigger at least searchable attrs."""
        client, idx = _mock_client()
        _configure_index(client, index_name)
        idx.update_searchable_attributes.assert_called_once()


# ---------------------------------------------------------------------------
# TestSafeIndex
# ---------------------------------------------------------------------------


class TestSafeIndex:
    """Tests for _safe_index (error-swallowing wrapper)."""

    @patch("lab_manager.services.search.get_search_client")
    def test_happy_path(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        docs = [{"id": 1, "name": "test"}]
        _safe_index("products", docs)
        client.index.assert_called_with("products")
        idx.add_documents.assert_called_once_with(docs, primary_key="id")

    @patch("lab_manager.services.search.get_search_client")
    def test_exception_is_swallowed(self, mock_get_client):
        """When Meilisearch is unavailable, _safe_index logs but does not raise."""
        mock_get_client.side_effect = Exception("connection refused")
        # Should not raise
        _safe_index("products", [{"id": 1}])

    @patch("lab_manager.services.search.get_search_client")
    def test_add_documents_failure_swallowed(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.add_documents.side_effect = Exception("timeout")
        # Should not raise
        _safe_index("products", [{"id": 1}])


# ---------------------------------------------------------------------------
# TestIndexRecordFunctions
# ---------------------------------------------------------------------------


class TestIndexProductRecord:
    @patch("lab_manager.services.search.get_search_client")
    def test_full_product(self, mock_get_client):
        from lab_manager.models.product import Product

        client, idx = _mock_client()
        mock_get_client.return_value = client
        p = Product(
            id=1,
            catalog_number="CAT-001",
            name="Acid",
            category="chemical",
            vendor_id=5,
        )
        index_product_record(p)
        client.index.assert_called_with("products")
        idx.add_documents.assert_called_once()
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["id"] == 1
        assert doc["catalog_number"] == "CAT-001"
        assert doc["name"] == "Acid"
        assert doc["category"] == "chemical"
        assert doc["vendor_id"] == 5

    @patch("lab_manager.services.search.get_search_client")
    def test_product_with_cas_number(self, mock_get_client):
        from lab_manager.models.product import Product

        client, idx = _mock_client()
        mock_get_client.return_value = client
        p = Product(
            id=2,
            catalog_number="CAT-002",
            name="Ethanol",
            cas_number="64-17-5",
            vendor_id=1,
        )
        index_product_record(p)
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["cas_number"] == "64-17-5"

    @patch("lab_manager.services.search.get_search_client")
    def test_product_optional_fields_none(self, mock_get_client):
        """Optional fields (category, cas_number, vendor_id) are None by default and should be skipped."""
        from lab_manager.models.product import Product

        client, idx = _mock_client()
        mock_get_client.return_value = client
        p = Product(id=3, catalog_number="CAT-003", name="Minimal")
        index_product_record(p)
        doc = idx.add_documents.call_args[0][0][0]
        assert "category" not in doc
        assert "cas_number" not in doc
        # vendor_id is None, should be skipped
        assert "vendor_id" not in doc

    @patch("lab_manager.services.search.get_search_client")
    def test_meilisearch_unavailable_no_crash(self, mock_get_client):
        from lab_manager.models.product import Product

        mock_get_client.side_effect = Exception("connection refused")
        p = Product(id=1, catalog_number="X", name="Y")
        # Should not raise
        index_product_record(p)


class TestIndexVendorRecord:
    @patch("lab_manager.services.search.get_search_client")
    def test_full_vendor(self, mock_get_client):
        from lab_manager.models.vendor import Vendor

        client, idx = _mock_client()
        mock_get_client.return_value = client
        v = Vendor(
            id=1,
            name="Sigma",
            aliases=["Sigma-Aldrich", "Merck"],
            website="https://sigma.com",
            email="info@sigma.com",
        )
        index_vendor_record(v)
        client.index.assert_called_with("vendors")
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["id"] == 1
        assert doc["name"] == "Sigma"
        assert doc["aliases"] == "Sigma-Aldrich, Merck"
        assert doc["website"] == "https://sigma.com"
        assert doc["email"] == "info@sigma.com"

    @patch("lab_manager.services.search.get_search_client")
    def test_aliases_string_not_list(self, mock_get_client):
        from lab_manager.models.vendor import Vendor

        client, idx = _mock_client()
        mock_get_client.return_value = client
        v = Vendor(id=2, name="V", aliases="just-a-string")
        index_vendor_record(v)
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["aliases"] == "just-a-string"

    @patch("lab_manager.services.search.get_search_client")
    def test_minimal_vendor(self, mock_get_client):
        from lab_manager.models.vendor import Vendor

        client, idx = _mock_client()
        mock_get_client.return_value = client
        v = Vendor(id=3, name="MinV")
        index_vendor_record(v)
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["id"] == 3
        assert doc["name"] == "MinV"
        assert "aliases" not in doc
        assert "website" not in doc
        assert "email" not in doc

    @patch("lab_manager.services.search.get_search_client")
    def test_empty_aliases_list(self, mock_get_client):
        from lab_manager.models.vendor import Vendor

        client, idx = _mock_client()
        mock_get_client.return_value = client
        v = Vendor(id=4, name="NoAlias", aliases=[])
        index_vendor_record(v)
        doc = idx.add_documents.call_args[0][0][0]
        assert "aliases" not in doc


class TestIndexOrderRecord:
    @patch("lab_manager.services.search.get_search_client")
    def test_full_order(self, mock_get_client):
        from lab_manager.models.order import Order

        client, idx = _mock_client()
        mock_get_client.return_value = client
        o = Order(
            id=10,
            po_number="PO-2026-001",
            order_date=date(2026, 3, 1),
            ship_date=date(2026, 3, 5),
            received_date=date(2026, 3, 10),
            received_by="Alice",
            status="received",
            delivery_number="DEL-001",
            invoice_number="INV-001",
            vendor_id=1,
        )
        index_order_record(o)
        client.index.assert_called_with("orders")
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["id"] == 10
        assert doc["po_number"] == "PO-2026-001"
        assert doc["order_date"] == "2026-03-01"
        assert doc["ship_date"] == "2026-03-05"
        assert doc["received_date"] == "2026-03-10"
        assert doc["received_by"] == "Alice"
        assert doc["status"] == "received"
        assert doc["delivery_number"] == "DEL-001"
        assert doc["invoice_number"] == "INV-001"
        assert doc["vendor_id"] == 1

    @patch("lab_manager.services.search.get_search_client")
    def test_order_with_none_fields(self, mock_get_client):
        from lab_manager.models.order import Order

        client, idx = _mock_client()
        mock_get_client.return_value = client
        o = Order(id=11, status="pending")
        index_order_record(o)
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["status"] == "pending"
        assert "po_number" not in doc
        assert "order_date" not in doc


class TestIndexOrderItemRecord:
    @patch("lab_manager.services.search.get_search_client")
    def test_full_order_item(self, mock_get_client):
        from lab_manager.models.order import OrderItem

        client, idx = _mock_client()
        mock_get_client.return_value = client
        item = OrderItem(
            id=1,
            catalog_number="CAT-1",
            description="Reagent X",
            lot_number="LOT-1",
            batch_number="BATCH-1",
            quantity=Decimal("5.0"),
            unit="mL",
            unit_price=Decimal("10.50"),
            order_id=10,
        )
        index_order_item_record(item)
        client.index.assert_called_with("order_items")
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["id"] == 1
        assert doc["catalog_number"] == "CAT-1"
        assert doc["description"] == "Reagent X"
        assert doc["lot_number"] == "LOT-1"
        assert doc["batch_number"] == "BATCH-1"
        # Decimal is serialized as string by _serialize_value
        assert isinstance(doc["quantity"], str)
        assert float(doc["quantity"]) == 5.0
        assert doc["unit"] == "mL"
        assert isinstance(doc["unit_price"], str)
        assert float(doc["unit_price"]) == 10.5
        assert doc["order_id"] == 10


class TestIndexDocumentRecord:
    @patch("lab_manager.services.search.get_search_client")
    def test_full_document(self, mock_get_client):
        from lab_manager.models.document import Document

        client, idx = _mock_client()
        mock_get_client.return_value = client
        doc = Document(
            id=1,
            file_path="/tmp/test.pdf",
            file_name="test.pdf",
            document_type="invoice",
            vendor_name="ACME Corp",
            status="pending",
            ocr_text="short text",
        )
        index_document_record(doc)
        client.index.assert_called_with("documents")
        sent = idx.add_documents.call_args[0][0][0]
        assert sent["id"] == 1
        assert sent["file_name"] == "test.pdf"
        assert sent["document_type"] == "invoice"
        assert sent["vendor_name"] == "ACME Corp"
        assert sent["status"] == "pending"
        assert sent["ocr_text"] == "short text"

    @patch("lab_manager.services.search.get_search_client")
    def test_ocr_text_truncated_at_5000(self, mock_get_client):
        from lab_manager.models.document import Document

        client, idx = _mock_client()
        mock_get_client.return_value = client
        long_text = "x" * 10000
        doc = Document(
            id=2,
            file_path="/tmp/long.pdf",
            file_name="long.pdf",
            ocr_text=long_text,
        )
        index_document_record(doc)
        sent = idx.add_documents.call_args[0][0][0]
        assert len(sent["ocr_text"]) == 5000
        assert sent["ocr_text"] == "x" * 5000

    @patch("lab_manager.services.search.get_search_client")
    def test_document_none_fields_omitted(self, mock_get_client):
        from lab_manager.models.document import Document

        client, idx = _mock_client()
        mock_get_client.return_value = client
        doc = Document(id=3, file_path="/tmp/min.pdf", file_name="min.pdf")
        index_document_record(doc)
        sent = idx.add_documents.call_args[0][0][0]
        assert "document_type" not in sent
        assert "vendor_name" not in sent
        assert "ocr_text" not in sent


class TestIndexInventoryRecord:
    @patch("lab_manager.services.search.get_search_client")
    def test_full_inventory(self, mock_get_client):
        from lab_manager.models.inventory import InventoryItem

        client, idx = _mock_client()
        mock_get_client.return_value = client
        item = InventoryItem(
            id=1,
            product_id=1,
            lot_number="LOT-99",
            quantity_on_hand=Decimal("25.5"),
            unit="EA",
            expiry_date=date(2027, 6, 15),
            status="available",
            notes="Store at 4C",
        )
        index_inventory_record(item)
        client.index.assert_called_with("inventory")
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["id"] == 1
        assert doc["lot_number"] == "LOT-99"
        assert doc["quantity_on_hand"] == 25.5
        assert doc["unit"] == "EA"
        assert doc["expiry_date"] == "2027-06-15"
        assert doc["status"] == "available"
        assert doc["notes"] == "Store at 4C"

    @patch("lab_manager.services.search.get_search_client")
    def test_inventory_null_quantity_defaults_to_zero(self, mock_get_client):
        from lab_manager.models.inventory import InventoryItem

        client, idx = _mock_client()
        mock_get_client.return_value = client
        item = InventoryItem(id=2, product_id=1, quantity_on_hand=None)
        index_inventory_record(item)
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["quantity_on_hand"] == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_inventory_none_fields_omitted(self, mock_get_client):
        from lab_manager.models.inventory import InventoryItem

        client, idx = _mock_client()
        mock_get_client.return_value = client
        item = InventoryItem(
            id=3,
            product_id=1,
            quantity_on_hand=Decimal("10"),
        )
        index_inventory_record(item)
        doc = idx.add_documents.call_args[0][0][0]
        assert "lot_number" not in doc
        assert "unit" not in doc
        assert "expiry_date" not in doc
        assert "notes" not in doc

    @patch("lab_manager.services.search.get_search_client")
    def test_inventory_decimal_quantity_converted_to_float(self, mock_get_client):
        from lab_manager.models.inventory import InventoryItem

        client, idx = _mock_client()
        mock_get_client.return_value = client
        item = InventoryItem(
            id=4,
            product_id=1,
            quantity_on_hand=Decimal("3.1415"),
        )
        index_inventory_record(item)
        doc = idx.add_documents.call_args[0][0][0]
        assert isinstance(doc["quantity_on_hand"], float)
        assert doc["quantity_on_hand"] == 3.1415


# ---------------------------------------------------------------------------
# TestSyncFunctions (batch indexing with DB)
# ---------------------------------------------------------------------------


class TestSyncProducts:
    @patch("lab_manager.services.search.get_search_client")
    def test_empty_db(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_products(db_session)
        assert count == 0
        idx.add_documents.assert_not_called()

    @patch("lab_manager.services.search.get_search_client")
    def test_indexes_existing_products(self, mock_get_client, db_session):
        from lab_manager.models.product import Product

        db_session.add(Product(catalog_number="C1", name="P1", vendor_id=None))
        db_session.add(Product(catalog_number="C2", name="P2", vendor_id=None))
        db_session.flush()

        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_products(db_session)
        assert count == 2
        idx.add_documents.assert_called_once()
        docs = idx.add_documents.call_args[0][0]
        assert len(docs) == 2
        assert idx.add_documents.call_args[1]["primary_key"] == "id"

    @patch("lab_manager.services.search.get_search_client")
    def test_configures_index_after_sync(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        sync_products(db_session)
        idx.update_searchable_attributes.assert_called_once()


class TestSyncVendors:
    @patch("lab_manager.services.search.get_search_client")
    def test_empty_db(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_vendors(db_session)
        assert count == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_indexes_vendor_with_aliases(self, mock_get_client, db_session):
        from lab_manager.models.vendor import Vendor

        db_session.add(Vendor(name="V1", aliases=["alias1", "alias2"]))
        db_session.flush()

        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_vendors(db_session)
        assert count == 1
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["aliases"] == "alias1, alias2"


class TestSyncOrders:
    @patch("lab_manager.services.search.get_search_client")
    def test_empty_db(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_orders(db_session)
        assert count == 0


class TestSyncOrderItems:
    @patch("lab_manager.services.search.get_search_client")
    def test_empty_db(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_order_items(db_session)
        assert count == 0


class TestSyncDocuments:
    @patch("lab_manager.services.search.get_search_client")
    def test_empty_db(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_documents(db_session)
        assert count == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_truncates_long_ocr_text(self, mock_get_client, db_session):
        from lab_manager.models.document import Document

        long_text = "A" * 8000
        db_session.add(
            Document(file_path="/tmp/a.pdf", file_name="a.pdf", ocr_text=long_text)
        )
        db_session.flush()

        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_documents(db_session)
        assert count == 1
        doc = idx.add_documents.call_args[0][0][0]
        assert len(doc["ocr_text"]) == 5000


class TestSyncInventory:
    @patch("lab_manager.services.search.get_search_client")
    def test_empty_db(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_inventory(db_session)
        assert count == 0

    @patch("lab_manager.services.search.get_search_client")
    def test_indexes_inventory_item(self, mock_get_client, db_session):
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

        client, idx = _mock_client()
        mock_get_client.return_value = client
        count = sync_inventory(db_session)
        assert count == 1
        doc = idx.add_documents.call_args[0][0][0]
        assert doc["quantity_on_hand"] == 10.0
        assert doc["expiry_date"] == "2027-01-01"


# ---------------------------------------------------------------------------
# TestSyncAll
# ---------------------------------------------------------------------------


class TestSyncAll:
    @patch("lab_manager.services.search.get_search_client")
    def test_returns_counts_for_all_indexes(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        counts = sync_all(db_session)
        assert isinstance(counts, dict)
        for index_name in INDEX_CONFIG:
            assert index_name in counts

    @patch("lab_manager.services.search.get_search_client")
    def test_clears_all_indexes_first(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        sync_all(db_session)
        # Should call delete_all_documents for each index in INDEX_CONFIG
        assert idx.delete_all_documents.call_count == len(INDEX_CONFIG)

    @patch("lab_manager.services.search.get_search_client")
    def test_delete_failure_records_error(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        # Make first delete fail, rest succeed
        idx.delete_all_documents.side_effect = [Exception("not found")] + [None] * 20
        counts = sync_all(db_session)
        assert "errors" in counts
        assert counts["errors"]["clear_index_failures"] >= 1

    @patch("lab_manager.services.search.get_search_client")
    def test_all_deletes_fail(self, mock_get_client, db_session):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.delete_all_documents.side_effect = Exception("down")
        counts = sync_all(db_session)
        assert counts["errors"]["clear_index_failures"] == len(INDEX_CONFIG)


# ---------------------------------------------------------------------------
# TestSearchFunction
# ---------------------------------------------------------------------------


class TestSearch:
    @patch("lab_manager.services.search.get_search_client")
    def test_basic_search(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": [{"id": 1, "name": "Result"}]}
        result = search("test")
        assert len(result) == 1
        assert result[0]["name"] == "Result"

    @patch("lab_manager.services.search.get_search_client")
    def test_custom_index_and_limit(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": []}
        search("query", index="vendors", limit=50)
        idx.search.assert_called_once_with("query", {"limit": 50})
        client.index.assert_called_with("vendors")

    @patch("lab_manager.services.search.get_search_client")
    def test_empty_results(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": []}
        result = search("nonexistent")
        assert result == []

    @patch("lab_manager.services.search.get_search_client")
    def test_default_limit_is_20(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": []}
        search("test")
        idx.search.assert_called_once_with("test", {"limit": 20})

    @patch("lab_manager.services.search.get_search_client")
    def test_default_index_is_products(self, mock_get_client):
        client, _ = _mock_client()
        mock_get_client.return_value = client
        client.index.return_value.search.return_value = {"hits": []}
        search("test")
        client.index.assert_called_with("products")


class TestSearchAll:
    @patch("lab_manager.services.search.get_search_client")
    def test_searches_all_indexes(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": [{"id": 1}]}
        result = search_all("test", limit=5)
        assert isinstance(result, dict)
        # All indexes should have results since mock returns hits for all
        for index_name in INDEX_CONFIG:
            assert index_name in result

    @patch("lab_manager.services.search.get_search_client")
    def test_skips_indexes_with_no_hits(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": []}
        result = search_all("test")
        assert result == {}

    @patch("lab_manager.services.search.get_search_client")
    def test_exception_skips_index_gracefully(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.side_effect = Exception("unavailable")
        result = search_all("test")
        assert result == {}

    @patch("lab_manager.services.search.get_search_client")
    def test_partial_failure(self, mock_get_client):
        """If one index fails, others still return results."""
        client = MagicMock()
        mock_get_client.return_value = client

        call_count = 0

        def fake_index(name):
            nonlocal call_count
            call_count += 1
            idx = MagicMock()
            if name == "products":
                idx.search.return_value = {"hits": [{"id": 1, "name": "found"}]}
            elif name == "vendors":
                idx.search.side_effect = Exception("timeout")
            else:
                idx.search.return_value = {"hits": []}
            return idx

        client.index = fake_index
        result = search_all("test")
        assert "products" in result
        assert "vendors" not in result

    @patch("lab_manager.services.search.get_search_client")
    def test_limit_passed_to_search(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": []}
        search_all("test", limit=42)
        idx.search.assert_called_with("test", {"limit": 42})


class TestSuggest:
    @patch("lab_manager.services.search.get_search_client")
    def test_returns_product_suggestions(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client

        call_count = 0

        def fake_search(query, opts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # products
                return {"hits": [{"id": 1, "name": "Acid", "catalog_number": "CAT-1"}]}
            if call_count == 2:  # vendors
                return {"hits": []}
            # order_items
            return {"hits": []}

        idx.search.side_effect = fake_search
        result = suggest("acid")
        assert len(result) == 1
        assert result[0]["type"] == "product"
        assert result[0]["text"] == "Acid"
        assert result[0]["catalog_number"] == "CAT-1"

    @patch("lab_manager.services.search.get_search_client")
    def test_returns_vendor_suggestions(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client

        call_count = 0

        def fake_search(query, opts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"hits": []}
            if call_count == 2:  # vendors
                return {"hits": [{"id": 5, "name": "Sigma"}]}
            return {"hits": []}

        idx.search.side_effect = fake_search
        result = suggest("sig")
        assert len(result) == 1
        assert result[0]["type"] == "vendor"
        assert result[0]["text"] == "Sigma"

    @patch("lab_manager.services.search.get_search_client")
    def test_returns_order_item_suggestions(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client

        call_count = 0

        def fake_search(query, opts):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"hits": []}
            # order_items
            return {
                "hits": [
                    {"id": 10, "catalog_number": "CAT-X", "description": "Reagent"}
                ]
            }

        idx.search.side_effect = fake_search
        result = suggest("cat")
        assert len(result) == 1
        assert result[0]["type"] == "order_item"
        assert result[0]["text"] == "CAT-X"

    @patch("lab_manager.services.search.get_search_client")
    def test_order_item_falls_back_to_description(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client

        call_count = 0

        def fake_search(query, opts):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {"hits": []}
            # order_items with no catalog_number
            return {"hits": [{"id": 11, "description": "Special Reagent"}]}

        idx.search.side_effect = fake_search
        result = suggest("spec")
        assert result[0]["text"] == "Special Reagent"

    @patch("lab_manager.services.search.get_search_client")
    def test_respects_limit(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client

        # Return 5 hits for each of 3 indexes (15 total)
        def fake_search(query, opts):
            limit = opts.get("limit", 10)
            if opts.get("attributesToRetrieve", []) == ["id", "name", "catalog_number"]:
                return {
                    "hits": [
                        {"id": i, "name": f"P{i}", "catalog_number": f"C{i}"}
                        for i in range(5)
                    ]
                }
            if opts.get("attributesToRetrieve", []) == ["id", "name"]:
                return {"hits": [{"id": i, "name": f"V{i}"} for i in range(5)]}
            return {"hits": [{"id": i, "catalog_number": f"O{i}"} for i in range(5)]}

        idx.search.side_effect = fake_search
        result = suggest("test", limit=3)
        assert len(result) <= 3

    @patch("lab_manager.services.search.get_search_client")
    def test_all_indexes_fail_returns_empty(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.side_effect = Exception("down")
        result = suggest("test")
        assert result == []

    @patch("lab_manager.services.search.get_search_client")
    def test_one_index_fails_others_succeed(self, mock_get_client):
        client = MagicMock()
        mock_get_client.return_value = client

        call_count = 0

        def fake_index(name):
            nonlocal call_count
            call_count += 1
            idx = MagicMock()
            if name == "products":
                idx.search.side_effect = Exception("fail")
            elif name == "vendors":
                idx.search.return_value = {"hits": [{"id": 1, "name": "V"}]}
            else:
                idx.search.return_value = {"hits": []}
            return idx

        client.index = fake_index
        result = suggest("test")
        assert any(r["type"] == "vendor" for r in result)

    @patch("lab_manager.services.search.get_search_client")
    def test_default_limit_is_10(self, mock_get_client):
        client, idx = _mock_client()
        mock_get_client.return_value = client
        idx.search.return_value = {"hits": []}
        suggest("test")
        # The first search call is for products with limit=10
        first_call = idx.search.call_args_list[0]
        assert first_call[0][1]["limit"] == 10


# ---------------------------------------------------------------------------
# TestGetSearchClient
# ---------------------------------------------------------------------------


class TestGetSearchClient:
    @patch("lab_manager.services.search.meilisearch.Client")
    @patch("lab_manager.services.search.get_settings")
    def test_creates_client_with_url_and_key(self, mock_settings, mock_client_cls):
        from lab_manager.config import Settings

        mock_settings.return_value = Settings(
            meilisearch_url="http://meili:7700",
            meilisearch_api_key="secret-key",
            auth_enabled=False,
        )
        get_search_client.cache_clear()
        client = get_search_client()
        mock_client_cls.assert_called_once_with("http://meili:7700", "secret-key")

    @patch("lab_manager.services.search.meilisearch.Client")
    @patch("lab_manager.services.search.get_settings")
    def test_empty_api_key_becomes_none(self, mock_settings, mock_client_cls):
        from lab_manager.config import Settings

        mock_settings.return_value = Settings(
            meilisearch_url="http://localhost:7700",
            meilisearch_api_key="",
            auth_enabled=False,
        )
        get_search_client.cache_clear()
        client = get_search_client()
        mock_client_cls.assert_called_once_with("http://localhost:7700", None)

    @patch("lab_manager.services.search.meilisearch.Client")
    @patch("lab_manager.services.search.get_settings")
    def test_cached_client_returned(self, mock_settings, mock_client_cls):
        from lab_manager.config import Settings

        mock_settings.return_value = Settings(
            meilisearch_url="http://localhost:7700",
            auth_enabled=False,
        )
        get_search_client.cache_clear()
        c1 = get_search_client()
        c2 = get_search_client()
        assert c1 is c2
        # Only one Client construction despite two calls
        assert mock_client_cls.call_count == 1


# ---------------------------------------------------------------------------
# TestBatchSizeConstant
# ---------------------------------------------------------------------------


class TestBatchSize:
    def test_batch_size_is_500(self):
        assert _BATCH_SIZE == 500


class TestIndexConfig:
    def test_all_indexes_have_searchable_attributes(self):
        for name, cfg in INDEX_CONFIG.items():
            assert "searchableAttributes" in cfg, f"{name} missing searchableAttributes"

    def test_all_indexes_have_filterable_attributes(self):
        for name, cfg in INDEX_CONFIG.items():
            assert "filterableAttributes" in cfg, f"{name} missing filterableAttributes"

    def test_all_indexes_have_sortable_attributes(self):
        for name, cfg in INDEX_CONFIG.items():
            assert "sortableAttributes" in cfg, f"{name} missing sortableAttributes"

    def test_expected_index_names(self):
        expected = {
            "products",
            "vendors",
            "orders",
            "order_items",
            "documents",
            "inventory",
        }
        assert set(INDEX_CONFIG.keys()) == expected
