"""Comprehensive unit tests for barcode lookup route.

Mocks the DB session and paginate helper to isolate route logic
from database interactions.  Covers:
  - Exact catalog_number matching
  - Partial/fuzzy matching across multiple fields
  - Priority ordering (exact over partial)
  - No-match fallback
  - Parameter validation (value, page, page_size)
  - Response structure
  - Edge cases (special characters, long codes, whitespace, Unicode)
  - Barcode format validation patterns
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lab_manager.config import get_settings


@pytest.fixture(autouse=True)
def _disable_auth():
    """Ensure auth is disabled for all tests in this module."""
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()
    yield
    os.environ.pop("AUTH_ENABLED", None)
    get_settings.cache_clear()


@pytest.fixture()
def mock_db():
    """A MagicMock stand-in for a SQLAlchemy Session."""
    return MagicMock()


@pytest.fixture()
def client(mock_db):
    """TestClient using create_app with mocked DB, AUTH_ENABLED=false."""
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c


def _paginated_result(
    items: list | None = None,
    total: int = 0,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Build a realistic paginate() return dict."""
    items = items if items is not None else []
    pages = (total + page_size - 1) // page_size if total else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


# ===================================================================
#  1.  Exact catalog_number matching
# ===================================================================


class TestExactCatalogNumberMatch:
    """Exact match on product.catalog_number returns match_type='catalog_number_exact'."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_match_returns_catalog_number_exact(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(
            items=[{"id": 1, "product_id": 10, "lot_number": "LOT-X"}],
            total=1,
        )
        resp = client.get("/api/v1/barcode/lookup?value=CAT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["match_type"] == "catalog_number_exact"
        assert data["total"] == 1

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_match_returns_correct_items(self, mock_paginate, client):
        items = [
            {"id": 1, "product_id": 10, "lot_number": "LOT-A"},
            {"id": 2, "product_id": 10, "lot_number": "LOT-B"},
        ]
        mock_paginate.return_value = _paginated_result(items=items, total=2)
        resp = client.get("/api/v1/barcode/lookup?value=CAT-002")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_match_paginate_called_once(self, mock_paginate, client):
        """When exact match succeeds, paginate should be called exactly once (no fuzzy)."""
        mock_paginate.return_value = _paginated_result(total=1)
        client.get("/api/v1/barcode/lookup?value=CAT-003")
        assert mock_paginate.call_count == 1

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_match_with_numeric_catalog(self, mock_paginate, client):
        """Catalog numbers can be purely numeric."""
        mock_paginate.return_value = _paginated_result(total=1)
        resp = client.get("/api/v1/barcode/lookup?value=1234567890")
        assert resp.status_code == 200
        assert resp.json()["match_type"] == "catalog_number_exact"


# ===================================================================
#  2.  Partial / fuzzy matching
# ===================================================================


class TestPartialFuzzyMatch:
    """When no exact match, fuzzy ILIKE search across multiple fields."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_partial_match_after_exact_empty(self, mock_paginate, client):
        """Exact returns 0, fuzzy returns 1 => match_type='partial'."""
        mock_paginate.side_effect = [
            _paginated_result(total=0, items=[]),
            _paginated_result(total=1, items=[{"id": 5}]),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=Ethanol")
        assert resp.status_code == 200
        assert resp.json()["match_type"] == "partial"
        assert mock_paginate.call_count == 2

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_partial_match_by_product_name(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(
                total=1, items=[{"id": 3, "product": {"name": "Sodium Chloride"}}]
            ),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=Sodium")
        assert resp.json()["match_type"] == "partial"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_partial_match_by_lot_number(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=1, items=[{"id": 7, "lot_number": "LOT-XYZ-2024"}]),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=LOT-XYZ")
        assert resp.json()["match_type"] == "partial"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_partial_match_by_cas_number(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(
                total=1, items=[{"id": 8, "product": {"cas_number": "64-17-5"}}]
            ),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=64-17")
        assert resp.json()["match_type"] == "partial"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_partial_match_paginate_called_twice(self, mock_paginate, client):
        """Exact miss + fuzzy hit => paginate called exactly twice."""
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=1),
        ]
        client.get("/api/v1/barcode/lookup?value=anything")
        assert mock_paginate.call_count == 2


# ===================================================================
#  3.  Priority: exact over partial
# ===================================================================


class TestExactOverPartialPriority:
    """When exact match exists, fuzzy query must NOT execute."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_wins_over_partial(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1)
        resp = client.get("/api/v1/barcode/lookup?value=CAT-WINS")
        assert resp.json()["match_type"] == "catalog_number_exact"
        # Only 1 call -- fuzzy never executed.
        assert mock_paginate.call_count == 1

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_empty_triggers_fuzzy(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=2),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=FUZZ")
        assert resp.json()["match_type"] == "partial"
        assert mock_paginate.call_count == 2


# ===================================================================
#  4.  No-match fallback
# ===================================================================


class TestNoMatchFallback:
    """When both exact and fuzzy return nothing."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_no_match_returns_none_type(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=0),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=NONEXISTENT")
        data = resp.json()
        assert data["match_type"] == "none"
        assert data["total"] == 0
        assert data["items"] == []
        assert data["pages"] == 0

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_no_match_preserves_pagination_params(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=0),
        ]
        resp = client.get("/api/v1/barcode/lookup?value=NOPE&page=3&page_size=25")
        data = resp.json()
        assert data["page"] == 3
        assert data["page_size"] == 25

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_no_match_paginate_called_twice(self, mock_paginate, client):
        """Both queries execute when there is no match."""
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=0),
        ]
        client.get("/api/v1/barcode/lookup?value=VOID")
        assert mock_paginate.call_count == 2


# ===================================================================
#  5.  Parameter validation
# ===================================================================


class TestParameterValidation:
    """FastAPI Query validation for value, page, page_size."""

    def test_missing_value_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup")
        assert resp.status_code == 422

    def test_empty_value_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup?value=")
        assert resp.status_code == 422

    def test_page_zero_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup?value=X&page=0")
        assert resp.status_code == 422

    def test_negative_page_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup?value=X&page=-1")
        assert resp.status_code == 422

    def test_page_size_zero_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup?value=X&page_size=0")
        assert resp.status_code == 422

    def test_page_size_exceeds_max_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup?value=X&page_size=201")
        assert resp.status_code == 422

    def test_page_size_negative_returns_422(self, client):
        resp = client.get("/api/v1/barcode/lookup?value=X&page_size=-5")
        assert resp.status_code == 422

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_valid_page_size_boundary_min(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=X&page_size=1")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_valid_page_size_boundary_max(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=X&page_size=200")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_page_param_accepted(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=X&page=5")
        assert resp.status_code == 200


# ===================================================================
#  6.  Response structure
# ===================================================================


class TestResponseStructure:
    """Every response must contain the canonical pagination + match_type keys."""

    REQUIRED_KEYS = {"items", "total", "page", "page_size", "pages", "match_type"}

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_match_response_keys(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1)
        data = client.get("/api/v1/barcode/lookup?value=CAT").json()
        assert self.REQUIRED_KEYS <= set(data.keys())

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_partial_match_response_keys(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=1),
        ]
        data = client.get("/api/v1/barcode/lookup?value=CAT").json()
        assert self.REQUIRED_KEYS <= set(data.keys())

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_no_match_response_keys(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=0),
        ]
        data = client.get("/api/v1/barcode/lookup?value=NOPE").json()
        assert self.REQUIRED_KEYS <= set(data.keys())

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_match_type_values_are_strings(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1)
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert isinstance(data["match_type"], str)

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_total_is_int(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=3)
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert isinstance(data["total"], int)

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_items_is_list(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1, items=[{"id": 1}])
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert isinstance(data["items"], list)

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_pages_is_int(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=10, page_size=5)
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert isinstance(data["pages"], int)

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_page_and_page_size_preserved(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0, page=2, page_size=10)
        data = client.get("/api/v1/barcode/lookup?value=X&page=2&page_size=10").json()
        assert data["page"] == 2
        assert data["page_size"] == 10


# ===================================================================
#  7.  Edge cases -- special characters, formats, lengths
# ===================================================================


class TestEdgeCaseBarcodeValues:
    """Various barcode value edge cases."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_single_character_value(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=A")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_long_barcode_value(self, mock_paginate, client):
        """Real barcodes can be long (e.g. GS1-128, QR data)."""
        long_val = "A" * 200
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get(f"/api/v1/barcode/lookup?value={long_val}")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_hyphens(self, mock_paginate, client):
        """Hyphens are common in catalog numbers (e.g. CAT-001-REV2)."""
        mock_paginate.return_value = _paginated_result(total=1)
        resp = client.get("/api/v1/barcode/lookup?value=CAT-001-REV2")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_dots(self, mock_paginate, client):
        """Dots appear in versioned catalog numbers."""
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=CAT.v2.1")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_slashes(self, mock_paginate, client):
        """Slashes appear in lot numbers and compound identifiers."""
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=LOT%2FA")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_parentheses(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=CAT%281%29")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_plus_sign(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=CAT%2B001")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_equals_sign(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=CAT%3D001")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_ampersand(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=A%26B")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_unicode_value(self, mock_paginate, client):
        """Some barcodes contain Unicode (e.g. QR codes with non-ASCII)."""
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=%E4%B8%AD%E6%96%87")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_value_with_percent_encoded_chars(self, mock_paginate, client):
        """Ensure URL-encoded characters are decoded by FastAPI before reaching the route."""
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=hello%20world")
        assert resp.status_code == 200

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_all_numeric_barcode(self, mock_paginate, client):
        """Typical EAN/UPC barcodes are purely numeric."""
        mock_paginate.return_value = _paginated_result(total=1)
        resp = client.get("/api/v1/barcode/lookup?value=4006381333931")
        assert resp.status_code == 200
        assert resp.json()["match_type"] == "catalog_number_exact"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_barcode_like_code128(self, mock_paginate, client):
        """Code 128 barcodes can contain full ASCII."""
        mock_paginate.return_value = _paginated_result(total=0)
        resp = client.get("/api/v1/barcode/lookup?value=CODE128%23TEST")
        assert resp.status_code == 200


# ===================================================================
#  8.  Pagination details
# ===================================================================


class TestPaginationDetails:
    """Pagination metadata correctness with mocked results."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_default_page_is_1(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0, page=1)
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert data["page"] == 1

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_default_page_size_is_50(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=0, page_size=50)
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert data["page_size"] == 50

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_custom_page_and_size_passed_through(self, mock_paginate, client):
        """The route passes page/page_size to paginate, which returns them."""
        mock_paginate.return_value = _paginated_result(total=100, page=3, page_size=10)
        data = client.get("/api/v1/barcode/lookup?value=X&page=3&page_size=10").json()
        assert data["page"] == 3
        assert data["page_size"] == 10
        assert data["total"] == 100
        # 100 items / 10 per page = 10 pages
        assert data["pages"] == 10


# ===================================================================
#  9.  Paginate mock interaction
# ===================================================================


class TestPaginateInteraction:
    """Verify the route calls paginate with correct arguments."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_query_passes_db_session(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1)
        client.get("/api/v1/barcode/lookup?value=CAT")
        _args, _kwargs = mock_paginate.call_args
        # Second positional arg is the db session
        assert len(_args) >= 2
        # The db is the mock we injected (not None)
        assert _args[1] is not None

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_exact_query_passes_page_params(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1)
        client.get("/api/v1/barcode/lookup?value=CAT&page=2&page_size=15")
        _args, _kwargs = mock_paginate.call_args
        assert _args[2] == 2  # page
        assert _args[3] == 15  # page_size

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_fuzzy_query_receives_same_page_params(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=1),
        ]
        client.get("/api/v1/barcode/lookup?value=FUZ&page=4&page_size=20")
        # Second call (fuzzy)
        fuzzy_args = mock_paginate.call_args_list[1]
        assert fuzzy_args[0][2] == 4
        assert fuzzy_args[0][3] == 20


# ===================================================================
#  10. Match type transitions
# ===================================================================


class TestMatchTypeTransitions:
    """Verify match_type values for all three branches."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_match_type_exact(self, mock_paginate, client):
        mock_paginate.return_value = _paginated_result(total=1)
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert data["match_type"] == "catalog_number_exact"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_match_type_partial(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=1),
        ]
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert data["match_type"] == "partial"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_match_type_none(self, mock_paginate, client):
        mock_paginate.side_effect = [
            _paginated_result(total=0),
            _paginated_result(total=0),
        ]
        data = client.get("/api/v1/barcode/lookup?value=X").json()
        assert data["match_type"] == "none"

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_all_valid_match_types(self, mock_paginate, client):
        """The only valid match_type values are catalog_number_exact, partial, none."""
        valid = {"catalog_number_exact", "partial", "none"}
        mock_paginate.return_value = _paginated_result(total=1)
        resp = client.get("/api/v1/barcode/lookup?value=X")
        assert resp.json()["match_type"] in valid


# ===================================================================
#  11. HTTP method constraints
# ===================================================================


class TestHTTPMethodConstraints:
    """The barcode lookup endpoint only accepts GET."""

    def test_post_not_allowed(self, client):
        resp = client.post("/api/v1/barcode/lookup?value=X")
        assert resp.status_code == 405

    def test_put_not_allowed(self, client):
        resp = client.put("/api/v1/barcode/lookup?value=X")
        assert resp.status_code == 405

    def test_delete_not_allowed(self, client):
        resp = client.delete("/api/v1/barcode/lookup?value=X")
        assert resp.status_code == 405

    def test_patch_not_allowed(self, client):
        resp = client.patch("/api/v1/barcode/lookup?value=X")
        assert resp.status_code == 405


# ===================================================================
#  12. Multiple items from same product
# ===================================================================


class TestMultipleItemsSameProduct:
    """One product can have multiple inventory items (different lots)."""

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_multiple_inventory_items_returned(self, mock_paginate, client):
        items = [
            {"id": 1, "product_id": 10, "lot_number": "LOT-A"},
            {"id": 2, "product_id": 10, "lot_number": "LOT-B"},
            {"id": 3, "product_id": 10, "lot_number": "LOT-C"},
        ]
        mock_paginate.return_value = _paginated_result(items=items, total=3)
        data = client.get("/api/v1/barcode/lookup?value=MULTI-CAT").json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @patch("lab_manager.api.routes.barcode.paginate")
    def test_large_result_set_paginated(self, mock_paginate, client):
        """Paginate handles truncation -- route just returns what paginate gives."""
        items = [{"id": i} for i in range(50)]
        mock_paginate.return_value = _paginated_result(items=items, total=150)
        data = client.get("/api/v1/barcode/lookup?value=BIG&page=1&page_size=50").json()
        assert data["total"] == 150
        assert len(data["items"]) == 50


# ===================================================================
#  13. Barcode format validation helpers
# ===================================================================


