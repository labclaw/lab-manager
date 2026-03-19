"""Step definitions for search and discovery BDD scenarios."""

from __future__ import annotations

import pytest
from meilisearch.errors import MeilisearchApiError
from pytest_bdd import given, parsers, scenario, then, when

from lab_manager.services.search import get_search_client

FEATURE = "../features/search.feature"


def _meilisearch_available() -> bool:
    """Return True only when Meilisearch is reachable and accepts authenticated requests."""
    try:
        # get_indexes() requires auth; health() does not — use the former.
        get_search_client().get_indexes()
        return True
    except Exception:
        return False


_requires_meilisearch = pytest.mark.skipif(
    not _meilisearch_available(),
    reason="Meilisearch not available or requires authentication",
)


# --- Scenarios ---


@_requires_meilisearch
@scenario(FEATURE, "Search across all indexes")
def test_search_across_all():
    pass


@_requires_meilisearch
@scenario(FEATURE, "Search for a specific vendor")
def test_search_vendor():
    pass


@_requires_meilisearch
@scenario(FEATURE, "Autocomplete suggestions")
def test_autocomplete():
    pass


@_requires_meilisearch
@scenario(FEATURE, "Search returns empty for unknown term")
def test_empty_search():
    pass


# --- Helpers ---


def _wait_for_meilisearch_task(client, task_uid: int, timeout_ms: int = 5000) -> None:
    """Wait for a Meilisearch indexing task to complete."""
    client.wait_for_task(task_uid, timeout_in_ms=timeout_ms)


def _index_documents(client, index_name: str, docs: list[dict]) -> None:
    """Add documents to a Meilisearch index and wait for completion."""
    task_info = client.index(index_name).add_documents(docs, primary_key="id")
    _wait_for_meilisearch_task(client, task_info.task_uid)


def _delete_all_indexes(client) -> None:
    """Delete all documents from known indexes to get a clean state."""
    for index_name in (
        "products",
        "vendors",
        "orders",
        "order_items",
        "documents",
        "inventory",
    ):
        try:
            task_info = client.index(index_name).delete_all_documents()
            _wait_for_meilisearch_task(client, task_info.task_uid)
        except MeilisearchApiError:
            pass  # Index may not exist yet


@pytest.fixture(autouse=True)
def clean_meilisearch_indexes():
    """Clean all Meilisearch indexes before each scenario."""
    client = get_search_client()
    _delete_all_indexes(client)
    yield
    _delete_all_indexes(client)


# --- Given steps ---


@given("the following data is indexed:", target_fixture="indexed_data")
def index_table_data(api, datatable):
    """Create vendors/products via API, then index them into Meilisearch.

    datatable from pytest-bdd 8.x is Sequence[Sequence[str]] where the first
    row is the header.
    """
    # Convert list-of-lists to list-of-dicts using the header row.
    header = [str(c) for c in datatable[0]]
    rows = [dict(zip(header, [str(c) for c in row])) for row in datatable[1:]]

    client = get_search_client()
    vendor_ids = {}
    product_docs = []
    vendor_docs = []

    # First pass: create vendors
    for row in rows:
        if row["type"] == "vendor":
            r = api.post("/api/vendors/", json={"name": row["name"]})
            assert r.status_code in (200, 201), r.text
            vendor = r.json()
            vendor_ids[row["name"]] = vendor["id"]
            vendor_docs.append({"id": vendor["id"], "name": vendor["name"]})

    # Ensure we have at least one vendor for products
    if not vendor_ids:
        r = api.post("/api/vendors/", json={"name": "Test Vendor"})
        assert r.status_code in (200, 201), r.text
        vendor = r.json()
        vendor_ids["Test Vendor"] = vendor["id"]

    default_vendor_id = next(iter(vendor_ids.values()))

    # Second pass: create products
    for row in rows:
        if row["type"] == "product":
            r = api.post(
                "/api/products/",
                json={
                    "name": row["name"],
                    "catalog_number": f"CAT-{row['name'][:10].upper().replace(' ', '')}",
                    "vendor_id": default_vendor_id,
                },
            )
            assert r.status_code in (200, 201), r.text
            product = r.json()
            product_docs.append({"id": product["id"], "name": product["name"]})

    # Index into Meilisearch
    if vendor_docs:
        _index_documents(client, "vendors", vendor_docs)
    if product_docs:
        _index_documents(client, "products", product_docs)

    return {
        "vendor_ids": vendor_ids,
        "product_docs": product_docs,
        "vendor_docs": vendor_docs,
    }


@given(
    parsers.parse('a vendor "{name}" exists and is indexed'),
    target_fixture="indexed_vendor",
)
def create_and_index_vendor(api, name):
    """Create a vendor via API and index it into Meilisearch."""
    r = api.post("/api/vendors/", json={"name": name})
    assert r.status_code in (200, 201), r.text
    vendor = r.json()

    client = get_search_client()
    _index_documents(client, "vendors", [{"id": vendor["id"], "name": vendor["name"]}])
    return vendor


@given(
    parsers.parse('products "{p1}", "{p2}", "{p3}" exist and are indexed'),
    target_fixture="indexed_products",
)
def create_and_index_products(api, p1, p2, p3):
    """Create three products via API and index them into Meilisearch."""
    # Need a vendor first
    r = api.post("/api/vendors/", json={"name": "Test Vendor"})
    assert r.status_code in (200, 201), r.text
    vendor = r.json()

    products = []
    for i, name in enumerate([p1, p2, p3], start=1):
        r = api.post(
            "/api/products/",
            json={
                "name": name,
                "catalog_number": f"SOD-{i:03d}",
                "vendor_id": vendor["id"],
            },
        )
        assert r.status_code in (200, 201), r.text
        products.append(r.json())

    # Index into Meilisearch
    client = get_search_client()
    docs = [
        {"id": p["id"], "name": p["name"], "catalog_number": p.get("catalog_number")}
        for p in products
    ]
    _index_documents(client, "products", docs)
    return products


# --- When steps ---


@when(parsers.parse('I search for "{query}"'), target_fixture="search_response")
def search_all_indexes(api, query):
    """Search across all indexes."""
    r = api.get("/api/search", params={"q": query})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I search for "{query}" in index "{index}"'),
    target_fixture="search_response",
)
def search_specific_index(api, query, index):
    """Search a specific index."""
    r = api.get("/api/search", params={"q": query, "index": index})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I request suggestions for "{query}"'),
    target_fixture="suggest_response",
)
def request_suggestions(api, query):
    """Request autocomplete suggestions."""
    r = api.get("/api/search/suggest", params={"q": query})
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse('I should get results from "{index}" index'))
def check_results_from_index(search_response, index):
    """Verify that search results include hits from the specified index."""
    results = search_response.get("results", {})
    assert index in results, (
        f"Expected results from '{index}' index, got indexes: {list(results.keys())}"
    )
    assert len(results[index]) > 0, f"No hits in '{index}' index"


@then(parsers.parse('the results should include "{name}"'))
def check_results_include(search_response, name):
    """Verify that the search results contain a hit with the given name."""
    results = search_response.get("results", {})
    all_hits = []
    for hits in results.values():
        all_hits.extend(hits)

    names = [h.get("name", "") for h in all_hits]
    assert name in names, f"Expected '{name}' in results, got: {names}"


@then(parsers.parse("I should get {count:d} result"))
def check_result_count_single(search_response, count):
    """Verify the number of hits in a single-index search."""
    hits = search_response.get("hits", [])
    assert len(hits) == count, f"Expected {count} results, got {len(hits)}"


@then(parsers.parse('the result name should be "{name}"'))
def check_result_name(search_response, name):
    """Verify the name of the first hit in a single-index search."""
    hits = search_response.get("hits", [])
    assert len(hits) > 0, "No hits returned"
    assert hits[0].get("name") == name, (
        f"Expected name '{name}', got '{hits[0].get('name')}'"
    )


@then(parsers.parse("I should get at least {count:d} suggestions"))
def check_min_suggestions(suggest_response, count):
    """Verify minimum number of autocomplete suggestions."""
    suggestions = suggest_response.get("suggestions", [])
    assert len(suggestions) >= count, (
        f"Expected at least {count} suggestions, got {len(suggestions)}"
    )


@then(parsers.parse('all suggestions should be of type "{type_name}"'))
def check_suggestion_types(suggest_response, type_name):
    """Verify that all suggestions are of the expected type."""
    suggestions = suggest_response.get("suggestions", [])
    assert len(suggestions) > 0, "No suggestions returned"
    for s in suggestions:
        assert s.get("type") == type_name, (
            f"Expected type '{type_name}', got '{s.get('type')}' for suggestion: {s}"
        )


@then(parsers.parse("I should get {count:d} total results"))
def check_total_results(search_response, count):
    """Verify the total number of results across all indexes."""
    total = search_response.get("total", 0)
    assert total == count, f"Expected {count} total results, got {total}"
