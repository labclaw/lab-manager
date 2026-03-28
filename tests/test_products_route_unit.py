"""Unit tests for products route -- CRUD, pagination, filters, enrichment, MSDS.

Uses direct function calls with MagicMock DB sessions to isolate route logic.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.api.routes.products import (
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    _CAS_RE,
    _PRODUCT_SORTABLE,
    _validate_cas,
    create_product,
    delete_product,
    enrich_product_endpoint,
    get_product,
    get_product_msds,
    get_pubchem_enrichment,
    list_product_inventory,
    list_product_orders,
    list_products,
    lookup_product_msds,
    update_product,
)
from lab_manager.exceptions import ConflictError, NotFoundError, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(
    id: int = 1,
    catalog_number: str = "CAT-001",
    name: str = "Test Reagent",
    vendor_id: int | None = 10,
    category: str | None = "chemicals",
    cas_number: str | None = "64-17-5",
    molecular_weight: float | None = None,
    molecular_formula: str | None = None,
    smiles: str | None = None,
    pubchem_cid: int | None = None,
    storage_temp: str | None = "2-8C",
    unit: str | None = "mL",
    hazard_info: str | None = None,
    hazard_class: str | None = None,
    msds_url: str | None = None,
    requires_safety_review: bool = False,
    extra: dict | None = None,
    is_active: bool = True,
) -> MagicMock:
    """Create a mock Product instance."""
    p = MagicMock()
    p.id = id
    p.catalog_number = catalog_number
    p.name = name
    p.vendor_id = vendor_id
    p.category = category
    p.cas_number = cas_number
    p.molecular_weight = molecular_weight
    p.molecular_formula = molecular_formula
    p.smiles = smiles
    p.pubchem_cid = pubchem_cid
    p.storage_temp = storage_temp
    p.unit = unit
    p.hazard_info = hazard_info
    p.hazard_class = hazard_class
    p.msds_url = msds_url
    p.requires_safety_review = requires_safety_review
    p.extra = extra or {}
    p.is_active = is_active
    p.created_at = datetime(2026, 1, 1, 0, 0, 0)
    p.updated_at = datetime(2026, 1, 1, 0, 0, 0)
    return p


def _make_db() -> MagicMock:
    """Create a mock DB session with sensible defaults."""
    db = MagicMock()
    db.get.return_value = None
    db.add.return_value = None
    db.flush.return_value = None
    db.refresh.side_effect = lambda obj: None
    db.delete.return_value = None
    db.rollback.return_value = None
    return db


def _make_paginate_result(items, total=None, page=1, page_size=50):
    """Build the dict that paginate() returns."""
    total = total if total is not None else len(items)
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


# ---------------------------------------------------------------------------
# CAS Validation
# ---------------------------------------------------------------------------


class TestCasValidation:
    """Test the _validate_cas helper and _CAS_RE regex."""

    def test_valid_cas(self):
        assert _validate_cas("64-17-5") == "64-17-5"

    def test_valid_cas_long_prefix(self):
        # 7-digit prefix is the max
        assert _validate_cas("1234567-89-0") == "1234567-89-0"

    def test_valid_cas_short_prefix(self):
        # 2-digit prefix is the min
        assert _validate_cas("10-20-1") == "10-20-1"

    def test_none_returns_none(self):
        assert _validate_cas(None) is None

    def test_empty_string_returns_none(self):
        assert _validate_cas("") is None

    def test_whitespace_only_returns_none(self):
        assert _validate_cas("   ") is None

    def test_strips_whitespace(self):
        assert _validate_cas("  64-17-5  ") == "64-17-5"

    def test_invalid_format_single_digit_prefix(self):
        with pytest.raises(ValueError, match="Invalid CAS number"):
            _validate_cas("1-23-4")

    def test_invalid_format_no_dashes(self):
        with pytest.raises(ValueError, match="Invalid CAS number"):
            _validate_cas("64175")

    def test_invalid_format_too_many_dashes(self):
        with pytest.raises(ValueError, match="Invalid CAS number"):
            _validate_cas("64-17-5-1")

    def test_invalid_format_trailing_letter(self):
        with pytest.raises(ValueError, match="Invalid CAS number"):
            _validate_cas("64-17-X")

    def test_cas_regex_pattern(self):
        assert _CAS_RE.match("64-17-5") is not None
        assert _CAS_RE.match("1234567-89-0") is not None
        assert _CAS_RE.match("1-23-4") is None


# ---------------------------------------------------------------------------
# ProductCreate Schema Validation
# ---------------------------------------------------------------------------


class TestProductCreateValidation:
    """Test Pydantic model validation for ProductCreate."""

    def test_valid_minimal(self):
        body = ProductCreate(catalog_number="CAT-001", name="Ethanol")
        assert body.catalog_number == "CAT-001"
        assert body.name == "Ethanol"
        assert body.vendor_id is None
        assert body.category is None
        assert body.cas_number is None
        assert body.storage_temp is None
        assert body.unit is None
        assert body.hazard_info is None
        assert body.extra == {}

    def test_valid_all_fields(self):
        body = ProductCreate(
            catalog_number="CAT-002",
            name="Methanol",
            vendor_id=5,
            category="solvents",
            cas_number="67-56-1",
            storage_temp="RT",
            unit="L",
            hazard_info="Flammable",
            extra={"color": "clear"},
        )
        assert body.vendor_id == 5
        assert body.category == "solvents"
        assert body.cas_number == "67-56-1"
        assert body.extra == {"color": "clear"}

    def test_empty_catalog_number_rejected(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="", name="Test")

    def test_blank_catalog_number_accepted_by_pydantic(self):
        """Pydantic min_length=1 allows whitespace-only strings."""
        body = ProductCreate(catalog_number="   ", name="Test")
        assert body.catalog_number == "   "

    def test_catalog_number_max_length(self):
        body = ProductCreate(catalog_number="A" * 100, name="Test")
        assert len(body.catalog_number) == 100

    def test_catalog_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="A" * 101, name="Test")

    def test_name_max_length(self):
        body = ProductCreate(catalog_number="C", name="B" * 500)
        assert len(body.name) == 500

    def test_name_exceeds_max_length(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="C", name="B" * 501)

    def test_invalid_cas_rejected(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="C", name="N", cas_number="bad-cas")

    def test_valid_cas_accepted(self):
        body = ProductCreate(catalog_number="C", name="N", cas_number="64-17-5")
        assert body.cas_number == "64-17-5"

    def test_none_cas_accepted(self):
        body = ProductCreate(catalog_number="C", name="N", cas_number=None)
        assert body.cas_number is None

    def test_category_max_length(self):
        body = ProductCreate(catalog_number="C", name="N", category="X" * 100)
        assert len(body.category) == 100

    def test_category_exceeds_max_length(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="C", name="N", category="X" * 101)

    def test_extra_default_empty_dict(self):
        body = ProductCreate(catalog_number="C", name="N")
        assert body.extra == {}

    def test_extra_custom_dict(self):
        body = ProductCreate(catalog_number="C", name="N", extra={"key": "val"})
        assert body.extra == {"key": "val"}

    def test_storage_temp_max_length(self):
        body = ProductCreate(catalog_number="C", name="N", storage_temp="X" * 50)
        assert len(body.storage_temp) == 50

    def test_storage_temp_exceeds_max_length(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="C", name="N", storage_temp="X" * 51)

    def test_hazard_info_max_length(self):
        body = ProductCreate(catalog_number="C", name="N", hazard_info="H" * 255)
        assert len(body.hazard_info) == 255

    def test_hazard_info_exceeds_max_length(self):
        with pytest.raises(Exception):
            ProductCreate(catalog_number="C", name="N", hazard_info="H" * 256)


# ---------------------------------------------------------------------------
# ProductUpdate Schema Validation
# ---------------------------------------------------------------------------


class TestProductUpdateValidation:
    """Test Pydantic model validation for ProductUpdate."""

    def test_all_none(self):
        body = ProductUpdate()
        assert body.catalog_number is None
        assert body.name is None
        assert body.vendor_id is None
        assert body.category is None
        assert body.cas_number is None
        assert body.storage_temp is None
        assert body.unit is None
        assert body.hazard_info is None
        assert body.hazard_class is None
        assert body.msds_url is None
        assert body.requires_safety_review is None
        assert body.extra is None

    def test_partial_update_name_only(self):
        body = ProductUpdate(name="New Name")
        assert body.name == "New Name"
        assert body.catalog_number is None

    def test_valid_cas(self):
        body = ProductUpdate(cas_number="64-17-5")
        assert body.cas_number == "64-17-5"

    def test_invalid_cas_rejected(self):
        with pytest.raises(Exception):
            ProductUpdate(cas_number="not-a-cas")

    def test_exclude_unset_behavior(self):
        """model_dump(exclude_unset=True) only includes explicitly set fields."""
        body = ProductUpdate(name="Updated", category="reagents")
        dumped = body.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "category" in dumped
        assert "catalog_number" not in dumped
        assert "vendor_id" not in dumped

    def test_empty_body_dumps_nothing(self):
        body = ProductUpdate()
        dumped = body.model_dump(exclude_unset=True)
        assert len(dumped) == 0

    def test_catalog_number_max_length(self):
        body = ProductUpdate(catalog_number="A" * 100)
        assert len(body.catalog_number) == 100

    def test_catalog_number_exceeds_max_length(self):
        with pytest.raises(Exception):
            ProductUpdate(catalog_number="A" * 101)

    def test_hazard_class_field(self):
        body = ProductUpdate(hazard_class="Flammable")
        assert body.hazard_class == "Flammable"

    def test_msds_url_field(self):
        body = ProductUpdate(msds_url="https://example.com/msds.pdf")
        assert body.msds_url == "https://example.com/msds.pdf"

    def test_requires_safety_review_field(self):
        body = ProductUpdate(requires_safety_review=True)
        assert body.requires_safety_review is True

    def test_extra_dict_field(self):
        body = ProductUpdate(extra={"new_key": "new_val"})
        assert body.extra == {"new_key": "new_val"}


# ---------------------------------------------------------------------------
# ProductResponse Schema
# ---------------------------------------------------------------------------


class TestProductResponse:
    """Test ProductResponse schema configuration."""

    def test_from_attributes_config(self):
        assert ProductResponse.model_config.get("from_attributes") is True

    def test_all_fields_present(self):
        fields = ProductResponse.model_fields
        expected_fields = {
            "id",
            "catalog_number",
            "name",
            "vendor_id",
            "category",
            "cas_number",
            "molecular_weight",
            "molecular_formula",
            "smiles",
            "pubchem_cid",
            "storage_temp",
            "unit",
            "hazard_info",
            "hazard_class",
            "msds_url",
            "requires_safety_review",
            "extra",
            "created_at",
            "updated_at",
        }
        assert expected_fields.issubset(set(fields.keys()))


# ---------------------------------------------------------------------------
# Sortable Columns Constant
# ---------------------------------------------------------------------------


class TestSortableColumns:
    """Test _PRODUCT_SORTABLE set."""

    def test_contains_expected_columns(self):
        expected = {
            "id",
            "created_at",
            "updated_at",
            "name",
            "catalog_number",
            "category",
            "vendor_id",
        }
        assert _PRODUCT_SORTABLE == expected

    def test_is_a_set(self):
        assert isinstance(_PRODUCT_SORTABLE, set)


# ---------------------------------------------------------------------------
# list_products
# ---------------------------------------------------------------------------


class TestListProducts:
    """Test the GET / products list endpoint."""

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_basic_list(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], total=0)
        db = _make_db()

        result = list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["total"] == 0
        assert result["items"] == []

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_calls_paginate(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_calls_apply_sort(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=25,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="name",
            sort_dir="desc",
            db=db,
        )
        mock_sort.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_with_vendor_filter(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=50,
            vendor_id=42,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_with_category_filter(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category="reagents",
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_with_catalog_number_filter(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category=None,
            catalog_number="CAT-001",
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_with_search_filter(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search="ethanol",
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_pagination_params(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([], page=3, page_size=10)
        db = _make_db()

        result = list_products(
            page=3,
            page_size=10,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["page"] == 3
        assert result["page_size"] == 10

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_no_filters_no_search(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        product = _make_product()
        mock_paginate.return_value = _make_paginate_result([product], total=1)
        db = _make_db()

        result = list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=False,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        assert result["total"] == 1
        assert len(result["items"]) == 1

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_include_inactive(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=50,
            vendor_id=None,
            category=None,
            catalog_number=None,
            search=None,
            include_inactive=True,
            sort_by="id",
            sort_dir="asc",
            db=db,
        )
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    @patch("lab_manager.api.routes.products.apply_sort")
    def test_list_all_filters_combined(self, mock_sort, mock_paginate):
        mock_sort.return_value = MagicMock()
        mock_paginate.return_value = _make_paginate_result([])
        db = _make_db()

        list_products(
            page=1,
            page_size=10,
            vendor_id=5,
            category="reagents",
            catalog_number="CAT",
            search="ethanol",
            include_inactive=False,
            sort_by="name",
            sort_dir="desc",
            db=db,
        )
        mock_paginate.assert_called_once()


# ---------------------------------------------------------------------------
# create_product
# ---------------------------------------------------------------------------


class TestCreateProduct:
    """Test the POST / products create endpoint."""

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_create_basic(self, mock_index):
        db = _make_db()
        body = ProductCreate(catalog_number="CAT-NEW", name="New Product")

        create_product(body=body, db=db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.refresh.assert_called_once()
        mock_index.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_create_with_all_fields(self, mock_index):
        db = _make_db()
        body = ProductCreate(
            catalog_number="CAT-FULL",
            name="Full Product",
            vendor_id=1,
            category="chemicals",
            cas_number="64-17-5",
            storage_temp="2-8C",
            unit="mL",
            hazard_info="Flammable",
            extra={"color": "blue"},
        )

        create_product(body=body, db=db)
        db.add.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_create_duplicate_catalog_raises_conflict(self, mock_index):
        from sqlalchemy.exc import IntegrityError

        db = _make_db()
        orig = MagicMock()
        orig.__str__ = lambda s: "uq_product_catalog_vendor"
        db.flush.side_effect = IntegrityError("", "", orig)

        body = ProductCreate(catalog_number="CAT-DUP", name="Dup Product")
        with pytest.raises(ConflictError, match="already exists"):
            create_product(body=body, db=db)

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_create_other_integrity_error_raises_conflict(self, mock_index):
        from sqlalchemy.exc import IntegrityError

        db = _make_db()
        orig = MagicMock()
        orig.__str__ = lambda s: "some_other_constraint"
        db.flush.side_effect = IntegrityError("", "", orig)

        body = ProductCreate(catalog_number="CAT-ERR", name="Err Product")
        with pytest.raises(ConflictError, match="Duplicate or constraint"):
            create_product(body=body, db=db)

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_create_rollback_on_integrity_error(self, mock_index):
        from sqlalchemy.exc import IntegrityError

        db = _make_db()
        orig = MagicMock()
        orig.__str__ = lambda s: "uq_product_catalog_vendor"
        db.flush.side_effect = IntegrityError("", "", orig)

        body = ProductCreate(catalog_number="CAT-DUP", name="Dup")
        with pytest.raises(ConflictError):
            create_product(body=body, db=db)
        db.rollback.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_create_indexes_product(self, mock_index):
        db = _make_db()
        body = ProductCreate(catalog_number="CAT-IDX", name="Indexed")

        create_product(body=body, db=db)
        mock_index.assert_called_once()


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------


class TestGetProduct:
    """Test the GET /{product_id} endpoint."""

    def test_get_existing(self):
        product = _make_product(id=42, name="Found Product")
        db = _make_db()
        db.get.return_value = product

        result = get_product(product_id=42, db=db)
        assert result.id == 42
        assert result.name == "Found Product"

    def test_get_nonexistent_raises_not_found(self):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_product(product_id=9999, db=db)

    def test_get_calls_db_get_with_product_model(self):
        from lab_manager.models.product import Product

        product = _make_product(id=5)
        db = _make_db()
        db.get.return_value = product

        get_product(product_id=5, db=db)
        db.get.assert_called_once_with(Product, 5)


# ---------------------------------------------------------------------------
# update_product
# ---------------------------------------------------------------------------


class TestUpdateProduct:
    """Test the PATCH /{product_id} endpoint."""

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_name(self, mock_index):
        product = _make_product(id=1, name="Old Name")
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate(name="New Name")
        update_product(product_id=1, body=body, db=db)

        assert product.name == "New Name"
        db.flush.assert_called_once()
        db.refresh.assert_called_once()
        mock_index.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_category(self, mock_index):
        product = _make_product(id=1, category="old_cat")
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate(category="new_cat")
        update_product(product_id=1, body=body, db=db)
        assert product.category == "new_cat"

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_cas_number(self, mock_index):
        product = _make_product(id=1, cas_number=None)
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate(cas_number="67-56-1")
        update_product(product_id=1, body=body, db=db)
        assert product.cas_number == "67-56-1"

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_safety_fields(self, mock_index):
        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate(
            hazard_class="Toxic",
            msds_url="https://example.com/msds.pdf",
            requires_safety_review=True,
        )
        update_product(product_id=1, body=body, db=db)
        assert product.hazard_class == "Toxic"
        assert product.msds_url == "https://example.com/msds.pdf"
        assert product.requires_safety_review is True

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_nonexistent_raises_not_found(self, mock_index):
        db = _make_db()
        db.get.return_value = None

        body = ProductUpdate(name="Nope")
        with pytest.raises(NotFoundError):
            update_product(product_id=9999, body=body, db=db)

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_duplicate_catalog_raises_conflict(self, mock_index):
        from sqlalchemy.exc import IntegrityError

        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        orig = MagicMock()
        orig.__str__ = lambda s: "uq_product_catalog_vendor"
        db.flush.side_effect = IntegrityError("", "", orig)

        body = ProductUpdate(catalog_number="CAT-DUP")
        with pytest.raises(ConflictError, match="already exists"):
            update_product(product_id=1, body=body, db=db)

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_other_integrity_error_raises_conflict(self, mock_index):
        from sqlalchemy.exc import IntegrityError

        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        orig = MagicMock()
        orig.__str__ = lambda s: "some_other_constraint"
        db.flush.side_effect = IntegrityError("", "", orig)

        body = ProductUpdate(vendor_id=99)
        with pytest.raises(ConflictError, match="Constraint violation"):
            update_product(product_id=1, body=body, db=db)

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_partial_update_only_sets_provided_fields(self, mock_index):
        product = _make_product(id=1, name="Keep This", category="keep_cat")
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate(category="new_cat")
        update_product(product_id=1, body=body, db=db)
        assert product.category == "new_cat"
        # name should not have been changed via setattr

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_empty_update_body_no_field_changes(self, mock_index):
        product = _make_product(id=1, name="Original")
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate()
        dumped = body.model_dump(exclude_unset=True)
        assert len(dumped) == 0

        update_product(product_id=1, body=body, db=db)
        db.flush.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_rollback_on_conflict(self, mock_index):
        from sqlalchemy.exc import IntegrityError

        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        orig = MagicMock()
        orig.__str__ = lambda s: "uq_product_catalog_vendor"
        db.flush.side_effect = IntegrityError("", "", orig)

        body = ProductUpdate(catalog_number="DUP")
        with pytest.raises(ConflictError):
            update_product(product_id=1, body=body, db=db)
        db.rollback.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    def test_update_extra_dict(self, mock_index):
        product = _make_product(id=1, extra={"old": "data"})
        db = _make_db()
        db.get.return_value = product

        body = ProductUpdate(extra={"new": "data"})
        update_product(product_id=1, body=body, db=db)
        assert product.extra == {"new": "data"}


# ---------------------------------------------------------------------------
# delete_product
# ---------------------------------------------------------------------------


class TestDeleteProduct:
    """Test the DELETE /{product_id} endpoint."""

    def test_delete_existing(self):
        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product

        result = delete_product(product_id=1, db=db)
        assert result is None
        db.delete.assert_called_once_with(product)
        db.flush.assert_called_once()

    def test_delete_nonexistent_raises_not_found(self):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            delete_product(product_id=9999, db=db)

    def test_delete_referenced_raises_conflict(self):
        from sqlalchemy.exc import IntegrityError

        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        db.flush.side_effect = IntegrityError("", "", MagicMock())

        with pytest.raises(ConflictError, match="Cannot delete product"):
            delete_product(product_id=1, db=db)

    def test_delete_referenced_rollback(self):
        from sqlalchemy.exc import IntegrityError

        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        db.flush.side_effect = IntegrityError("", "", MagicMock())

        with pytest.raises(ConflictError):
            delete_product(product_id=1, db=db)
        db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# list_product_inventory
# ---------------------------------------------------------------------------


class TestListProductInventory:
    """Test the GET /{product_id}/inventory endpoint."""

    @patch("lab_manager.api.routes.products.paginate")
    def test_basic_list(self, mock_paginate):
        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        mock_paginate.return_value = _make_paginate_result([])

        result = list_product_inventory(product_id=1, page=1, page_size=50, db=db)
        assert result["items"] == []
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    def test_product_not_found(self, mock_paginate):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            list_product_inventory(product_id=9999, page=1, page_size=50, db=db)

    @patch("lab_manager.api.routes.products.paginate")
    def test_pagination_params(self, mock_paginate):
        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        mock_paginate.return_value = _make_paginate_result([], page=2, page_size=10)

        result = list_product_inventory(product_id=1, page=2, page_size=10, db=db)
        assert result["page"] == 2
        assert result["page_size"] == 10


# ---------------------------------------------------------------------------
# list_product_orders
# ---------------------------------------------------------------------------


class TestListProductOrders:
    """Test the GET /{product_id}/orders endpoint."""

    @patch("lab_manager.api.routes.products.paginate")
    def test_basic_list(self, mock_paginate):
        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        mock_paginate.return_value = _make_paginate_result([])

        result = list_product_orders(product_id=1, page=1, page_size=50, db=db)
        assert result["items"] == []
        mock_paginate.assert_called_once()

    @patch("lab_manager.api.routes.products.paginate")
    def test_product_not_found(self, mock_paginate):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            list_product_orders(product_id=9999, page=1, page_size=50, db=db)

    @patch("lab_manager.api.routes.products.paginate")
    def test_pagination_params(self, mock_paginate):
        product = _make_product(id=1)
        db = _make_db()
        db.get.return_value = product
        mock_paginate.return_value = _make_paginate_result([], page=2, page_size=10)

        result = list_product_orders(product_id=1, page=2, page_size=10, db=db)
        assert result["page"] == 2
        assert result["page_size"] == 10


# ---------------------------------------------------------------------------
# get_pubchem_enrichment
# ---------------------------------------------------------------------------


class TestGetPubchemEnrichment:
    """Test the GET /{product_id}/pubchem endpoint."""

    @patch("lab_manager.services.pubchem.enrich_product")
    def test_returns_enrichment_data(self, mock_enrich):
        product = _make_product(id=1, name="Ethanol", catalog_number="CAT-001")
        db = _make_db()
        db.get.return_value = product
        mock_enrich.return_value = {"cas_number": "64-17-5"}

        result = get_pubchem_enrichment(product_id=1, db=db)

        assert result["product_id"] == 1
        assert result["enrichment"] == {"cas_number": "64-17-5"}
        mock_enrich.assert_called_once_with("Ethanol", "CAT-001")

    def test_product_not_found(self):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_pubchem_enrichment(product_id=9999, db=db)


# ---------------------------------------------------------------------------
# enrich_product_endpoint
# ---------------------------------------------------------------------------


class TestEnrichProductEndpoint:
    """Test the POST /{product_id}/enrich endpoint."""

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.pubchem.enrich_product")
    def test_enrich_fills_empty_fields(self, mock_enrich, mock_index):
        product = _make_product(
            id=1,
            name="Ethanol",
            cas_number=None,
            molecular_weight=None,
            molecular_formula=None,
            smiles=None,
            pubchem_cid=None,
        )
        db = _make_db()
        db.get.return_value = product

        mock_enrich.return_value = {
            "cas_number": "64-17-5",
            "molecular_weight": 46.07,
            "molecular_formula": "C2H6O",
            "smiles": "CCO",
            "pubchem_cid": 702,
        }

        enrich_product_endpoint(product_id=1, db=db)

        assert product.cas_number == "64-17-5"
        assert product.molecular_weight == 46.07
        assert product.molecular_formula == "C2H6O"
        assert product.smiles == "CCO"
        assert product.pubchem_cid == 702

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.pubchem.enrich_product")
    def test_enrich_does_not_overwrite_existing(self, mock_enrich, mock_index):
        product = _make_product(
            id=1,
            name="Ethanol",
            cas_number="EXISTING-CAS",
            molecular_weight=99.99,
        )
        db = _make_db()
        db.get.return_value = product

        mock_enrich.return_value = {
            "cas_number": "64-17-5",
            "molecular_weight": 46.07,
        }

        enrich_product_endpoint(product_id=1, db=db)

        # Should NOT overwrite existing values
        assert product.cas_number == "EXISTING-CAS"
        assert product.molecular_weight == 99.99

    @patch("lab_manager.services.pubchem.enrich_product")
    def test_enrich_product_not_found(self, mock_enrich):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            enrich_product_endpoint(product_id=9999, db=db)


# ---------------------------------------------------------------------------
# get_product_msds
# ---------------------------------------------------------------------------


class TestGetProductMsds:
    """Test the GET /{product_id}/msds endpoint."""

    def test_product_not_found(self):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            get_product_msds(product_id=9999, db=db)

    @patch("lab_manager.services.msds.get_safety_alert")
    def test_returns_basic_msds_info(self, mock_alert):
        product = _make_product(
            id=1,
            name="Ethanol",
            cas_number="64-17-5",
            msds_url="https://example.com/msds.pdf",
            hazard_class="Flammable",
            requires_safety_review=True,
        )
        db = _make_db()
        db.get.return_value = product
        mock_alert.return_value = "Warning: Flammable liquid"

        result = get_product_msds(product_id=1, db=db)

        assert result["product_id"] == 1
        assert result["name"] == "Ethanol"
        assert result["cas_number"] == "64-17-5"
        assert result["msds_url"] == "https://example.com/msds.pdf"
        assert result["hazard_class"] == "Flammable"
        assert result["requires_safety_review"] is True
        assert result["safety_alert"] == "Warning: Flammable liquid"

    @patch("lab_manager.services.msds.get_safety_alert")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_auto_lookup_when_cas_but_no_msds(self, mock_lookup, mock_alert):
        product = _make_product(
            id=1,
            name="Ethanol",
            cas_number="64-17-5",
            msds_url=None,
            hazard_class=None,
        )
        db = _make_db()
        db.get.return_value = product

        mock_lookup.return_value = {
            "msds_url": "https://auto.com/msds.pdf",
            "hazard_class": "Flammable",
            "signal_word": "Danger",
            "requires_safety_review": True,
        }
        mock_alert.return_value = "Auto alert"

        result = get_product_msds(product_id=1, db=db)

        assert result["msds_url"] == "https://auto.com/msds.pdf"
        assert result["hazard_class"] == "Flammable"
        assert result["signal_word"] == "Danger"
        assert result["safety_alert"] == "Auto alert"

    @patch("lab_manager.services.msds.get_safety_alert")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_no_auto_lookup_when_msds_exists(self, mock_lookup, mock_alert):
        product = _make_product(
            id=1,
            name="Ethanol",
            cas_number="64-17-5",
            msds_url="https://existing.com/msds.pdf",
            hazard_class="Flammable",
        )
        db = _make_db()
        db.get.return_value = product
        mock_alert.return_value = "Alert"

        result = get_product_msds(product_id=1, db=db)

        # lookup_msds should NOT be called since msds_url already exists
        mock_lookup.assert_not_called()
        assert result["msds_url"] == "https://existing.com/msds.pdf"

    def test_no_safety_alert_when_no_hazard_class(self):
        product = _make_product(
            id=1,
            name="Water",
            cas_number="7732-18-5",
            msds_url="https://example.com/water.pdf",
            hazard_class=None,
        )
        db = _make_db()
        db.get.return_value = product

        with patch("lab_manager.services.msds.get_safety_alert") as mock_alert:
            result = get_product_msds(product_id=1, db=db)

        mock_alert.assert_not_called()
        assert result["safety_alert"] is None

    def test_no_cas_and_no_msds_returns_defaults(self):
        product = _make_product(
            id=1,
            name="Unknown",
            cas_number=None,
            msds_url=None,
            hazard_class=None,
        )
        db = _make_db()
        db.get.return_value = product

        with patch("lab_manager.services.msds.lookup_msds") as mock_lookup:
            result = get_product_msds(product_id=1, db=db)

        mock_lookup.assert_not_called()
        assert result["signal_word"] is None
        assert result["safety_alert"] is None
        assert result["msds_url"] is None


# ---------------------------------------------------------------------------
# lookup_product_msds
# ---------------------------------------------------------------------------


class TestLookupProductMsds:
    """Test the POST /{product_id}/lookup-msds endpoint."""

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_successful_lookup(self, mock_lookup, mock_index):
        product = _make_product(
            id=1, cas_number="64-17-5", msds_url=None, hazard_class=None
        )
        db = _make_db()
        db.get.return_value = product

        mock_lookup.return_value = {
            "msds_url": "https://found.com/msds.pdf",
            "hazard_class": "Flammable",
            "requires_safety_review": True,
        }

        lookup_product_msds(product_id=1, db=db)

        assert product.msds_url == "https://found.com/msds.pdf"
        assert product.hazard_class == "Flammable"
        assert product.requires_safety_review is True
        db.flush.assert_called_once()
        db.refresh.assert_called_once()
        mock_index.assert_called_once()

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_does_not_overwrite_existing_msds_url(self, mock_lookup, mock_index):
        product = _make_product(
            id=1,
            cas_number="64-17-5",
            msds_url="https://existing.com/msds.pdf",
            hazard_class=None,
        )
        db = _make_db()
        db.get.return_value = product

        mock_lookup.return_value = {
            "msds_url": "https://new.com/msds.pdf",
            "hazard_class": "Toxic",
        }

        lookup_product_msds(product_id=1, db=db)

        # Should NOT overwrite existing msds_url
        assert product.msds_url == "https://existing.com/msds.pdf"
        # But hazard_class was None so it should be set
        assert product.hazard_class == "Toxic"

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_does_not_overwrite_existing_hazard_class(self, mock_lookup, mock_index):
        product = _make_product(
            id=1,
            cas_number="64-17-5",
            msds_url=None,
            hazard_class="ExistingClass",
        )
        db = _make_db()
        db.get.return_value = product

        mock_lookup.return_value = {
            "msds_url": "https://new.com/msds.pdf",
            "hazard_class": "NewClass",
        }

        lookup_product_msds(product_id=1, db=db)

        assert product.hazard_class == "ExistingClass"
        assert product.msds_url == "https://new.com/msds.pdf"

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_requires_safety_review_set_to_true(self, mock_lookup, mock_index):
        product = _make_product(
            id=1, cas_number="64-17-5", requires_safety_review=False
        )
        db = _make_db()
        db.get.return_value = product

        mock_lookup.return_value = {
            "msds_url": "https://msds.com/sds.pdf",
            "hazard_class": "Oxidizer",
            "requires_safety_review": True,
        }

        lookup_product_msds(product_id=1, db=db)

        assert product.requires_safety_review is True

    def test_no_cas_raises_validation_error(self):
        product = _make_product(id=1, cas_number=None)
        db = _make_db()
        db.get.return_value = product

        with pytest.raises(ValidationError, match="no CAS number"):
            lookup_product_msds(product_id=1, db=db)

    def test_product_not_found(self):
        db = _make_db()
        db.get.return_value = None

        with pytest.raises(NotFoundError):
            lookup_product_msds(product_id=9999, db=db)

    @patch("lab_manager.api.routes.products.index_product_record")
    @patch("lab_manager.services.msds.lookup_msds")
    def test_lookup_msds_no_data_returns_product(self, mock_lookup, mock_index):
        product = _make_product(
            id=1, cas_number="64-17-5", msds_url=None, hazard_class=None
        )
        db = _make_db()
        db.get.return_value = product

        mock_lookup.return_value = {}  # empty result

        lookup_product_msds(product_id=1, db=db)

        db.flush.assert_called_once()
        mock_index.assert_called_once()
