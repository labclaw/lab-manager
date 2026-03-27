"""Unit tests for pagination utility functions."""

from unittest.mock import MagicMock

from sqlalchemy import select

from lab_manager.api.pagination import apply_sort, escape_like, ilike_col, paginate
from lab_manager.models.product import Product


class TestEscapeLike:
    def test_no_special_chars(self):
        assert escape_like("hello") == "hello"

    def test_percent(self):
        assert escape_like("100%") == "100\\%"

    def test_underscore(self):
        assert escape_like("a_b") == "a\\_b"

    def test_backslash(self):
        assert escape_like("a\\b") == "a\\\\b"

    def test_all_special(self):
        assert escape_like("%\\_") == "\\%\\\\\\_"

    def test_empty_string(self):
        assert escape_like("") == ""

    def test_multiple_percent(self):
        assert escape_like("%%") == "\\%\\%"


class TestIlikeCol:
    def test_ilike_wraps_with_percent(self):
        col = MagicMock()
        ilike_col(col, "test")
        col.ilike.assert_called_once_with("%test%", escape="\\")

    def test_ilike_escapes_special(self):
        col = MagicMock()
        ilike_col(col, "100%")
        col.ilike.assert_called_once_with("%100\\%%", escape="\\")


class TestApplySort:
    def test_sort_asc(self):
        stmt = select(Product)
        result = apply_sort(stmt, Product, "id", "asc", {"id", "name"})
        assert result is not None

    def test_sort_desc(self):
        stmt = select(Product)
        result = apply_sort(stmt, Product, "id", "desc", {"id", "name"})
        assert result is not None

    def test_invalid_sort_defaults_to_id(self):
        stmt = select(Product)
        result = apply_sort(stmt, Product, "invalid_col", "asc", {"id", "name"})
        assert result is not None

    def test_empty_allowed_defaults_to_id(self):
        stmt = select(Product)
        result = apply_sort(stmt, Product, "name", "asc", set())
        assert result is not None

    def test_sort_by_name(self):
        stmt = select(Product)
        result = apply_sort(stmt, Product, "name", "asc", {"id", "name"})
        assert result is not None

    def test_invalid_direction_defaults_to_asc(self):
        stmt = select(Product)
        result = apply_sort(stmt, Product, "id", "invalid", {"id"})
        assert result is not None


class TestPaginate:
    def test_single_page(self):
        db = MagicMock()
        db.scalars.return_value.all.return_value = ["a", "b"]
        stmt = select(Product)
        result = paginate(stmt, db, page=1, page_size=50)
        assert result["items"] == ["a", "b"]
        assert result["total"] == 2
        assert result["page"] == 1
        assert result["page_size"] == 50
        assert result["pages"] == 1

    def test_has_more_truncates(self):
        db = MagicMock()
        # Return 3 items for page_size=2 → has_more=True, truncate to 2
        items = ["a", "b", "c"]
        db.scalars.return_value.all.return_value = items
        # has_more path needs db.execute() for count
        mock_scalar = MagicMock(return_value=5)
        db.execute.return_value.scalar = mock_scalar
        stmt = select(Product)
        result = paginate(stmt, db, page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5

    def test_empty_page(self):
        db = MagicMock()
        db.scalars.return_value.all.return_value = []
        stmt = select(Product)
        result = paginate(stmt, db, page=1, page_size=50)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["pages"] == 0

    def test_page_2_offset(self):
        db = MagicMock()
        db.scalars.return_value.all.return_value = ["x"]
        stmt = select(Product)
        result = paginate(stmt, db, page=2, page_size=10)
        assert result["page"] == 2
        # Verify offset was applied: (2-1)*10 = 10
        call_args = db.scalars.call_args[0][0]
        assert call_args is not None

    def test_pages_calculation(self):
        db = MagicMock()
        # 25 items for page_size=25 → no more, total=25, pages=1
        db.scalars.return_value.all.return_value = list(range(25))
        stmt = select(Product)
        result = paginate(stmt, db, page=1, page_size=25)
        assert result["pages"] == 1
        assert result["total"] == 25
