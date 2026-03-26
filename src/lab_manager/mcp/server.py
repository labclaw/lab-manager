"""MCP server exposing lab-manager inventory tools.

Run via:
    python -m lab_manager.mcp
    uv run mcp run src/lab_manager/mcp/server.py

Tools:
    - search_inventory: Full-text search across all lab indexes
    - get_inventory_status: Low stock + expiring items summary
    - search_documents: Search uploaded lab documents
    - get_analytics: Dashboard summary (spending, counts, stock levels)
    - ask_lab: Natural language Q&A over the lab database (RAG)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Lab-manager API base URL — configurable via environment variable
_BASE_URL = os.environ.get("LAB_MANAGER_URL", "http://localhost:8000")

# Optional API key for authenticated lab-manager instances
_API_KEY = os.environ.get("LAB_MANAGER_API_KEY", "")

mcp = FastMCP(
    "Lab Manager",
    instructions=(
        "Lab inventory management tools. Use these to query inventory, "
        "search documents, check stock levels, view analytics, and ask "
        "natural language questions about the lab database."
    ),
)


def _client() -> httpx.Client:
    """Create an httpx client with auth headers if configured."""
    headers: dict[str, str] = {"Accept": "application/json"}
    if _API_KEY:
        headers["X-API-Key"] = _API_KEY
    return httpx.Client(base_url=_BASE_URL, headers=headers, timeout=30.0)


def _format_json(data: Any) -> str:
    """Format data as readable JSON string."""
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


@mcp.tool()
def search_inventory(query: str, index: str = "", limit: int = 20) -> str:
    """Search lab inventory across all indexes (products, vendors, orders, documents, inventory).

    Args:
        query: Search text (product name, catalog number, vendor, etc.)
        index: Optional specific index to search (products, vendors, orders, documents, inventory, order_items). Leave empty to search all.
        limit: Maximum number of results per index (1-100, default 20).
    """
    params: dict[str, Any] = {"q": query, "limit": min(max(limit, 1), 100)}
    if index:
        params["index"] = index

    with _client() as client:
        resp = client.get("/api/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    # Format results for readability
    if index:
        hits = data.get("hits", [])
        if not hits:
            return f"No results found for '{query}' in {index}."
        return f"Found {len(hits)} results in {index}:\n{_format_json(hits)}"

    results = data.get("results", {})
    total = data.get("total", 0)
    if total == 0:
        return f"No results found for '{query}'."

    parts = [f"Found {total} total results for '{query}':"]
    for idx_name, hits in results.items():
        parts.append(f"\n--- {idx_name} ({len(hits)} hits) ---")
        parts.append(_format_json(hits))
    return "\n".join(parts)


@mcp.tool()
def get_inventory_status() -> str:
    """Get a summary of inventory status: low stock items, expiring items, and overall counts.

    Returns dashboard data including items expiring within 30 days,
    products below minimum stock levels, and order/inventory breakdowns.
    """
    with _client() as client:
        resp = client.get("/api/analytics/dashboard")
        resp.raise_for_status()
        data = resp.json()

    parts = ["## Lab Inventory Status\n"]

    # Counts
    parts.append(f"- Products: {data.get('total_products', 0)}")
    parts.append(f"- Vendors: {data.get('total_vendors', 0)}")
    parts.append(f"- Orders: {data.get('total_orders', 0)}")
    parts.append(f"- Inventory items: {data.get('total_inventory_items', 0)}")
    parts.append(f"- Documents: {data.get('total_documents', 0)}")
    parts.append(f"- Low stock products: {data.get('low_stock_count', 0)}")

    # Documents status
    parts.append("\n### Documents")
    parts.append(f"- Pending review: {data.get('documents_pending_review', 0)}")
    parts.append(f"- Approved: {data.get('documents_approved', 0)}")

    # Orders by status
    orders_status = data.get("orders_by_status", {})
    if orders_status:
        parts.append("\n### Orders by Status")
        for status, count in orders_status.items():
            parts.append(f"- {status}: {count}")

    # Inventory by status
    inv_status = data.get("inventory_by_status", {})
    if inv_status:
        parts.append("\n### Inventory by Status")
        for status, count in inv_status.items():
            parts.append(f"- {status}: {count}")

    # Expiring items
    expiring = data.get("expiring_soon", [])
    if expiring:
        parts.append(f"\n### Expiring Soon ({len(expiring)} items)")
        for item in expiring[:10]:
            parts.append(
                f"- {item.get('product_name', 'Unknown')} "
                f"(lot: {item.get('lot_number', 'N/A')}, "
                f"qty: {item.get('quantity_on_hand', 'N/A')}, "
                f"expires: {item.get('expiry_date', 'N/A')})"
            )
        if len(expiring) > 10:
            parts.append(f"  ... and {len(expiring) - 10} more")
    else:
        parts.append("\n### Expiring Soon\nNo items expiring within 30 days.")

    return "\n".join(parts)


@mcp.tool()
def search_documents(query: str, limit: int = 20) -> str:
    """Search uploaded lab documents (packing lists, invoices, COAs, shipping labels).

    Args:
        query: Search text (file name, vendor name, document type, OCR text content).
        limit: Maximum number of results (1-100, default 20).
    """
    params = {"q": query, "index": "documents", "limit": min(max(limit, 1), 100)}

    with _client() as client:
        resp = client.get("/api/search", params=params)
        resp.raise_for_status()
        data = resp.json()

    hits = data.get("hits", [])
    if not hits:
        return f"No documents found matching '{query}'."

    parts = [f"Found {len(hits)} documents matching '{query}':\n"]
    for doc in hits:
        parts.append(
            f"- [{doc.get('document_type', 'unknown')}] {doc.get('file_name', 'unnamed')} "
            f"(vendor: {doc.get('vendor_name', 'N/A')}, status: {doc.get('status', 'N/A')})"
        )
    return "\n".join(parts)


@mcp.tool()
def get_analytics() -> str:
    """Get lab analytics: spending by vendor, inventory value, top products, and monthly trends.

    Returns a comprehensive summary of lab spending patterns, most-ordered products,
    and current inventory valuation.
    """
    with _client() as client:
        # Fetch multiple analytics endpoints in sequence
        dashboard_resp = client.get("/api/analytics/dashboard")
        dashboard_resp.raise_for_status()
        dashboard = dashboard_resp.json()

        spending_resp = client.get("/api/analytics/spending-by-vendor")
        spending_resp.raise_for_status()
        spending = spending_resp.json()

        value_resp = client.get("/api/analytics/inventory-value")
        value_resp.raise_for_status()
        inv_value = value_resp.json()

        top_resp = client.get("/api/analytics/top-products", params={"limit": 10})
        top_resp.raise_for_status()
        top_prods = top_resp.json()

        monthly_resp = client.get("/api/analytics/spending-by-month")
        monthly_resp.raise_for_status()
        monthly = monthly_resp.json()

    parts = ["## Lab Analytics Summary\n"]

    # Overview
    parts.append("### Overview")
    parts.append(f"- Total products: {dashboard.get('total_products', 0)}")
    parts.append(f"- Total vendors: {dashboard.get('total_vendors', 0)}")
    parts.append(f"- Total orders: {dashboard.get('total_orders', 0)}")
    parts.append(
        f"- Inventory value: ${inv_value.get('total_value', 0):,.2f} "
        f"({inv_value.get('item_count', 0)} items)"
    )
    parts.append(f"- Low stock warnings: {dashboard.get('low_stock_count', 0)}")

    # Spending by vendor
    if spending:
        parts.append("\n### Top Vendors by Spending")
        for v in spending[:10]:
            parts.append(
                f"- {v.get('vendor_name', 'Unknown')}: "
                f"${v.get('total_spend', 0):,.2f} "
                f"({v.get('order_count', 0)} orders)"
            )

    # Top products
    if top_prods:
        parts.append("\n### Most Ordered Products")
        for p in top_prods[:10]:
            parts.append(
                f"- {p.get('name', p.get('catalog_number', 'Unknown'))} "
                f"({p.get('catalog_number', 'N/A')}, {p.get('vendor', 'N/A')}): "
                f"ordered {p.get('times_ordered', 0)}x"
            )

    # Monthly spending
    if monthly:
        parts.append("\n### Monthly Spending (last 12 months)")
        for m in monthly[-6:]:
            parts.append(
                f"- {m.get('month', 'N/A')}: "
                f"${m.get('total_spend', 0):,.2f} "
                f"({m.get('order_count', 0)} orders)"
            )

    return "\n".join(parts)


@mcp.tool()
def ask_lab(question: str) -> str:
    """Ask a natural language question about the lab database.

    Uses NL-to-SQL translation to answer questions like:
    - "How many products do we have from Sigma-Aldrich?"
    - "What items are expiring this month?"
    - "Show me all orders received in March"
    - "What's our total spending on antibodies?"

    Supports both English and Chinese questions.

    Args:
        question: Natural language question about lab inventory, orders, vendors, etc.
    """
    with _client() as client:
        resp = client.post(
            "/api/v1/ask",
            json={"question": question},
        )
        resp.raise_for_status()
        data = resp.json()

    answer = data.get("answer", "No answer generated.")
    source = data.get("source", "unknown")
    row_count = data.get("row_count")

    parts = [answer]
    if row_count is not None:
        parts.append(f"\n[Source: {source}, {row_count} rows returned]")

    return "\n".join(parts)


def main():
    """Entry point for running the MCP server."""
    mcp.run(transport="stdio")
