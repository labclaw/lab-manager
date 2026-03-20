"""Unified search API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from lab_manager.services.search import search, search_all, suggest

router = APIRouter()


@router.get("/")
def search_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    index: Optional[str] = Query(
        None, description="Specific index to search (omit for all)"
    ),
    limit: int = Query(20, ge=1, le=100, description="Max results per index"),
) -> dict:
    """Search across all indexes or a specific one."""
    if index:
        hits = search(q, index=index, limit=limit)
        return {"query": q, "index": index, "hits": hits, "count": len(hits)}
    
    # search_all returns a dict of index -> list of hits
    results_raw = search_all(q, limit=limit)
    # Ensure all hits are dicts, not raw Meilisearch Hit objects
    results = {idx: [dict(h) for h in hits] for idx, hits in results_raw.items()}
    total = sum(len(hits) for hits in results.values())
    return {"query": q, "results": results, "total": total}


@router.get("/suggest")
def suggest_endpoint(
    q: str = Query(..., min_length=1, description="Autocomplete query"),
    limit: int = Query(10, ge=1, le=50, description="Max suggestions"),
) -> dict:
    """Quick autocomplete suggestions (product names, vendor names, catalog numbers)."""
    suggestions = suggest(q, limit=limit)
    return {"query": q, "suggestions": suggestions}
