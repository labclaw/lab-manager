"""Meilisearch integration for full-text search."""

from __future__ import annotations

import meilisearch
from sqlalchemy.orm import Session

from lab_manager.config import get_settings
from lab_manager.models.product import Product
from lab_manager.models.order import OrderItem


def get_search_client():
    settings = get_settings()
    return meilisearch.Client(settings.meilisearch_url, settings.meilisearch_api_key)


def sync_products(db: Session):
    """Sync all products to Meilisearch."""
    client = get_search_client()
    products = db.query(Product).all()
    docs = [
        {
            "id": p.id,
            "catalog_number": p.catalog_number,
            "name": p.name,
            "category": p.category,
            "cas_number": p.cas_number,
            "vendor_id": p.vendor_id,
        }
        for p in products
    ]
    if docs:
        client.index("products").add_documents(docs)


def sync_orders(db: Session):
    """Sync order items to Meilisearch for search."""
    client = get_search_client()
    items = db.query(OrderItem).all()
    docs = [
        {
            "id": i.id,
            "catalog_number": i.catalog_number,
            "description": i.description,
            "lot_number": i.lot_number,
            "order_id": i.order_id,
        }
        for i in items
    ]
    if docs:
        client.index("order_items").add_documents(docs)


def search(query: str, index: str = "products", limit: int = 20) -> list[dict]:
    """Search across indexed data."""
    client = get_search_client()
    result = client.index(index).search(query, {"limit": limit})
    return result["hits"]
