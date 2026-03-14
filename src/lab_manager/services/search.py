"""Meilisearch integration for full-text search."""

from __future__ import annotations

import logging

import meilisearch
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.services.serialization import serialize_value as _serialize_value
from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.order import Order, OrderItem
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.document import Document

logger = logging.getLogger(__name__)

# Per-index configuration: searchable and filterable attributes
INDEX_CONFIG: dict[str, dict] = {
    "products": {
        "searchableAttributes": [
            "name",
            "catalog_number",
            "cas_number",
            "category",
        ],
        "filterableAttributes": ["vendor_id", "category"],
        "sortableAttributes": ["name"],
    },
    "vendors": {
        "searchableAttributes": [
            "name",
            "aliases",
            "website",
            "email",
        ],
        "filterableAttributes": [],
        "sortableAttributes": ["name"],
    },
    "orders": {
        "searchableAttributes": [
            "po_number",
            "delivery_number",
            "invoice_number",
            "received_by",
            "status",
        ],
        "filterableAttributes": ["vendor_id", "status"],
        "sortableAttributes": ["order_date"],
    },
    "order_items": {
        "searchableAttributes": [
            "catalog_number",
            "description",
            "lot_number",
            "batch_number",
        ],
        "filterableAttributes": ["order_id"],
        "sortableAttributes": [],
    },
    "documents": {
        "searchableAttributes": [
            "file_name",
            "vendor_name",
            "document_type",
            "ocr_text",
        ],
        "filterableAttributes": ["document_type", "status", "vendor_name"],
        "sortableAttributes": ["file_name"],
    },
    "inventory": {
        "searchableAttributes": [
            "lot_number",
            "status",
            "notes",
            "unit",
        ],
        "filterableAttributes": ["status"],
        "sortableAttributes": ["expiry_date"],
    },
}


def get_search_client() -> meilisearch.Client:
    settings = get_settings()
    api_key = settings.meilisearch_api_key or None
    return meilisearch.Client(settings.meilisearch_url, api_key)


def _make_doc(obj: object, fields: list[str]) -> dict:
    """Build a Meilisearch document from a DB row, skipping None values."""
    doc: dict = {}
    for f in fields:
        val = getattr(obj, f, None)
        val = _serialize_value(val)
        if val is not None:
            doc[f] = val
    return doc


def _configure_index(client: meilisearch.Client, index_name: str) -> None:
    """Apply searchable/filterable/sortable settings to an index."""
    cfg = INDEX_CONFIG.get(index_name, {})
    idx = client.index(index_name)
    if "searchableAttributes" in cfg:
        idx.update_searchable_attributes(cfg["searchableAttributes"])
    if "filterableAttributes" in cfg:
        idx.update_filterable_attributes(cfg["filterableAttributes"])
    if "sortableAttributes" in cfg:
        idx.update_sortable_attributes(cfg["sortableAttributes"])


def sync_products(db: Session) -> int:
    """Sync all products to Meilisearch."""
    client = get_search_client()
    fields = ["id", "catalog_number", "name", "category", "cas_number", "vendor_id"]
    products = db.query(Product).all()
    docs = [_make_doc(p, fields) for p in products]
    if docs:
        client.index("products").add_documents(docs, primary_key="id")
    _configure_index(client, "products")
    logger.info("Indexed %d products", len(docs))
    return len(docs)


def sync_vendors(db: Session) -> int:
    """Sync all vendors to Meilisearch."""
    client = get_search_client()
    vendors = db.query(Vendor).all()
    docs = []
    for v in vendors:
        d: dict = {"id": v.id}
        if v.name:
            d["name"] = v.name
        # Flatten aliases list to a comma-separated string
        if v.aliases:
            d["aliases"] = (
                ", ".join(v.aliases) if isinstance(v.aliases, list) else str(v.aliases)
            )
        if v.website:
            d["website"] = v.website
        if v.email:
            d["email"] = v.email
        docs.append(d)
    if docs:
        client.index("vendors").add_documents(docs, primary_key="id")
    _configure_index(client, "vendors")
    logger.info("Indexed %d vendors", len(docs))
    return len(docs)


def sync_orders(db: Session) -> int:
    """Sync all orders to Meilisearch."""
    client = get_search_client()
    fields = [
        "id",
        "po_number",
        "order_date",
        "ship_date",
        "received_date",
        "received_by",
        "status",
        "delivery_number",
        "invoice_number",
        "vendor_id",
    ]
    orders = db.query(Order).all()
    docs = [_make_doc(o, fields) for o in orders]
    if docs:
        client.index("orders").add_documents(docs, primary_key="id")
    _configure_index(client, "orders")
    logger.info("Indexed %d orders", len(docs))
    return len(docs)


def sync_order_items(db: Session) -> int:
    """Sync order items to Meilisearch."""
    client = get_search_client()
    fields = [
        "id",
        "catalog_number",
        "description",
        "lot_number",
        "batch_number",
        "quantity",
        "unit",
        "unit_price",
        "order_id",
    ]
    items = db.query(OrderItem).all()
    docs = [_make_doc(i, fields) for i in items]
    if docs:
        client.index("order_items").add_documents(docs, primary_key="id")
    _configure_index(client, "order_items")
    logger.info("Indexed %d order_items", len(docs))
    return len(docs)


def sync_documents(db: Session) -> int:
    """Sync documents to Meilisearch (ocr_text truncated to 5000 chars)."""
    client = get_search_client()
    documents = db.query(Document).all()
    docs = []
    for doc in documents:
        d: dict = {"id": doc.id}
        if doc.file_name:
            d["file_name"] = doc.file_name
        if doc.document_type:
            d["document_type"] = doc.document_type
        if doc.vendor_name:
            d["vendor_name"] = doc.vendor_name
        if doc.status:
            d["status"] = doc.status
        if doc.ocr_text:
            d["ocr_text"] = doc.ocr_text[:5000]
        docs.append(d)
    if docs:
        client.index("documents").add_documents(docs, primary_key="id")
    _configure_index(client, "documents")
    logger.info("Indexed %d documents", len(docs))
    return len(docs)


def sync_inventory(db: Session) -> int:
    """Sync inventory items to Meilisearch."""
    client = get_search_client()
    items = db.query(InventoryItem).all()
    docs = []
    for item in items:
        d: dict = {"id": item.id}
        if item.lot_number:
            d["lot_number"] = item.lot_number
        d["quantity_on_hand"] = item.quantity_on_hand
        if item.unit:
            d["unit"] = item.unit
        if item.expiry_date:
            d["expiry_date"] = item.expiry_date.isoformat()
        if item.status:
            d["status"] = item.status
        if item.notes:
            d["notes"] = item.notes
        docs.append(d)
    if docs:
        client.index("inventory").add_documents(docs, primary_key="id")
    _configure_index(client, "inventory")
    logger.info("Indexed %d inventory items", len(docs))
    return len(docs)


def sync_all(db: Session) -> dict[str, int]:
    """Full reindex of all tables into Meilisearch. Returns counts per index."""
    counts: dict[str, int] = {}
    counts["products"] = sync_products(db)
    counts["vendors"] = sync_vendors(db)
    counts["orders"] = sync_orders(db)
    counts["order_items"] = sync_order_items(db)
    counts["documents"] = sync_documents(db)
    counts["inventory"] = sync_inventory(db)
    logger.info("sync_all complete: %s", counts)
    return counts


def search(query: str, index: str = "products", limit: int = 20) -> list[dict]:
    """Search a single index."""
    client = get_search_client()
    result = client.index(index).search(query, {"limit": limit})
    return result["hits"]


def search_all(query: str, limit: int = 20) -> dict[str, list[dict]]:
    """Search across ALL indexes and merge results keyed by index name."""
    client = get_search_client()
    results: dict[str, list[dict]] = {}
    for index_name in INDEX_CONFIG:
        try:
            resp = client.index(index_name).search(query, {"limit": limit})
            hits = resp.get("hits", [])
            if hits:
                results[index_name] = hits
        except Exception:
            logger.warning("Index %s not available, skipping", index_name)
    return results


def suggest(query: str, limit: int = 10) -> list[dict]:
    """Quick autocomplete suggestions from products, vendors, and order_items."""
    client = get_search_client()
    suggestions: list[dict] = []

    # Products: name and catalog_number
    try:
        resp = client.index("products").search(
            query,
            {"limit": limit, "attributesToRetrieve": ["id", "name", "catalog_number"]},
        )
        for hit in resp.get("hits", []):
            suggestions.append(
                {
                    "type": "product",
                    "text": hit.get("name", ""),
                    "id": hit["id"],
                    "catalog_number": hit.get("catalog_number"),
                }
            )
    except Exception:
        pass

    # Vendors: name
    try:
        resp = client.index("vendors").search(
            query, {"limit": limit, "attributesToRetrieve": ["id", "name"]}
        )
        for hit in resp.get("hits", []):
            suggestions.append(
                {"type": "vendor", "text": hit.get("name", ""), "id": hit["id"]}
            )
    except Exception:
        pass

    # Order items: catalog_number
    try:
        resp = client.index("order_items").search(
            query,
            {
                "limit": limit,
                "attributesToRetrieve": ["id", "catalog_number", "description"],
            },
        )
        for hit in resp.get("hits", []):
            text = hit.get("catalog_number") or hit.get("description", "")
            suggestions.append({"type": "order_item", "text": text, "id": hit["id"]})
    except Exception:
        pass

    return suggestions[:limit]
