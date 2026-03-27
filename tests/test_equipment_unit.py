"""Unit tests for equipment route handler functions.

Uses MagicMock for DB sessions -- no database required.
Tests cover CRUD, status validation, filtering, sorting, pagination,
input validation, soft-delete, and error handling.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from lab_manager.api.routes.equipment import (
    EquipmentCreate,
    EquipmentUpdate,
    _SORTABLE,
    _VALID_EQUIPMENT_STATUSES,
    create_equipment,
    delete_equipment,
    get_equipment,
    list_equipment,
    update_equipment,
)
from lab_manager.exceptions import NotFoundError
from lab_manager.models.equipment import Equipment, EquipmentStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_equipment(**overrides) -> Equipment:
    """Build a mock Equipment instance with sensible defaults."""
    defaults = {
        "id": 1,
        "name": "Test Centrifuge",
        "manufacturer": "Eppendorf",
        "model": "5702R",
        "serial_number": "SN-001",
        "system_id": "SYS-001",
        "category": "centrifuge",
        "description": "A benchtop centrifuge",
        "location_id": None,
        "room": "Room 101",
        "estimated_value": Decimal("5000.00"),
        "status": EquipmentStatus.active,
        "is_api_controllable": False,
        "api_interface": None,
        "notes": None,
        "photos": [],
        "extracted_data": None,
        "extra": {},
    }
    defaults.update(overrides)
    equip = MagicMock(spec=Equipment)
    for k, v in defaults.items():
        setattr(equip, k, v)
    return equip


def _call_list(
    *,
    page=1,
    page_size=50,
    category=None,
    status=None,
    manufacturer=None,
    search=None,
    sort_by="id",
    sort_dir="asc",
    db=None,
):
    """Call list_equipment with all params explicit (avoids FastAPI Query defaults)."""
    return list_equipment(
        page=page,
        page_size=page_size,
        category=category,
        status=status,
        manufacturer=manufacturer,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        db=db or MagicMock(),
    )


# ---------------------------------------------------------------------------
# EquipmentCreate schema validation
# ---------------------------------------------------------------------------


class TestEquipmentCreateSchema:
    """Pydantic validation tests for EquipmentCreate."""

    def test_valid_minimal(self):
        body = EquipmentCreate(name="Scope")
        assert body.name == "Scope"
        assert body.status == EquipmentStatus.active
        assert body.manufacturer is None
        assert body.is_api_controllable is False

    def test_valid_all_fields(self):
        body = EquipmentCreate(
            name="NMR Spectrometer",
            manufacturer="Bruker",
            model="Avance III",
            serial_number="SN-999",
            system_id="SYS-999",
            category="spectroscopy",
            description="600 MHz NMR",
            location_id=5,
            room="Room 200",
            estimated_value=Decimal("500000"),
            status=EquipmentStatus.active,
            is_api_controllable=True,
            api_interface="tcp",
            notes="Calibrated",
            photos=["/img/a.jpg"],
            extracted_data={"source": "test"},
            extra={"key": "val"},
        )
        assert body.manufacturer == "Bruker"
        assert body.estimated_value == Decimal("500000")
        assert body.is_api_controllable is True

    def test_name_min_length_1(self):
        with pytest.raises(Exception):
            EquipmentCreate(name="")

    def test_name_max_length_500(self):
        EquipmentCreate(name="x" * 500)
        with pytest.raises(Exception):
            EquipmentCreate(name="x" * 501)

    def test_manufacturer_max_length_255(self):
        EquipmentCreate(name="ok", manufacturer="x" * 255)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", manufacturer="x" * 256)

    def test_model_max_length_255(self):
        EquipmentCreate(name="ok", model="x" * 255)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", model="x" * 256)

    def test_serial_number_max_length_255(self):
        EquipmentCreate(name="ok", serial_number="x" * 255)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", serial_number="x" * 256)

    def test_system_id_max_length_100(self):
        EquipmentCreate(name="ok", system_id="x" * 100)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", system_id="x" * 101)

    def test_category_max_length_100(self):
        EquipmentCreate(name="ok", category="x" * 100)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", category="x" * 101)

    def test_description_max_length_5000(self):
        EquipmentCreate(name="ok", description="d" * 5000)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", description="d" * 5001)

    def test_estimated_value_non_negative(self):
        EquipmentCreate(name="ok", estimated_value=Decimal("0"))
        EquipmentCreate(name="ok", estimated_value=Decimal("999.99"))
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", estimated_value=Decimal("-1"))

    def test_status_valid_values(self):
        for status in _VALID_EQUIPMENT_STATUSES:
            body = EquipmentCreate(name="ok", status=status)
            assert body.status == status

    def test_status_invalid_rejected(self):
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", status="unknown_status")

    def test_api_interface_max_length_100(self):
        EquipmentCreate(name="ok", api_interface="x" * 100)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", api_interface="x" * 101)

    def test_notes_max_length_5000(self):
        EquipmentCreate(name="ok", notes="n" * 5000)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", notes="n" * 5001)

    def test_room_max_length_100(self):
        EquipmentCreate(name="ok", room="r" * 100)
        with pytest.raises(Exception):
            EquipmentCreate(name="ok", room="r" * 101)

    def test_default_photos_empty_list(self):
        body = EquipmentCreate(name="ok")
        assert body.photos == []

    def test_default_extra_empty_dict(self):
        body = EquipmentCreate(name="ok")
        assert body.extra == {}


# ---------------------------------------------------------------------------
# EquipmentUpdate schema validation
# ---------------------------------------------------------------------------


class TestEquipmentUpdateSchema:
    """Pydantic validation tests for EquipmentUpdate."""

    def test_all_fields_optional(self):
        body = EquipmentUpdate()
        assert body.name is None
        assert body.status is None
        assert body.manufacturer is None

    def test_partial_update_name_only(self):
        body = EquipmentUpdate(name="New Name")
        assert body.name == "New Name"
        assert body.status is None

    def test_name_min_length_1(self):
        with pytest.raises(Exception):
            EquipmentUpdate(name="")

    def test_name_max_length_500(self):
        EquipmentUpdate(name="x" * 500)
        with pytest.raises(Exception):
            EquipmentUpdate(name="x" * 501)

    def test_status_valid_values(self):
        for status in _VALID_EQUIPMENT_STATUSES:
            body = EquipmentUpdate(status=status)
            assert body.status == status

    def test_status_none_allowed(self):
        body = EquipmentUpdate(status=None)
        assert body.status is None

    def test_status_invalid_rejected(self):
        with pytest.raises(Exception):
            EquipmentUpdate(status="invalid_status")

    def test_estimated_value_non_negative(self):
        EquipmentUpdate(estimated_value=Decimal("0"))
        with pytest.raises(Exception):
            EquipmentUpdate(estimated_value=Decimal("-0.01"))

    def test_manufacturer_max_length_255(self):
        EquipmentUpdate(manufacturer="x" * 255)
        with pytest.raises(Exception):
            EquipmentUpdate(manufacturer="x" * 256)

    def test_exclude_unset_behavior(self):
        body = EquipmentUpdate(name="Changed", status=EquipmentStatus.broken)
        dumped = body.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "status" in dumped
        assert "manufacturer" not in dumped


# ---------------------------------------------------------------------------
# create_equipment handler
# ---------------------------------------------------------------------------


class TestCreateEquipment:
    """Tests for the create_equipment route handler."""

    def test_creates_equipment_with_all_fields(self):
        db = MagicMock()
        body = EquipmentCreate(
            name="Spectrometer",
            manufacturer="Bruker",
            model="Avance",
            category="nmr",
        )

        result = create_equipment(body, db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        db.refresh.assert_called_once()
        # Verify the object passed to db.add has correct fields
        added_obj = db.add.call_args[0][0]
        assert added_obj.name == "Spectrometer"
        assert added_obj.manufacturer == "Bruker"

    def test_creates_with_default_status(self):
        db = MagicMock()
        body = EquipmentCreate(name="Default Status Equip")

        result = create_equipment(body, db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.status == EquipmentStatus.active

    def test_creates_with_explicit_status(self):
        db = MagicMock()
        body = EquipmentCreate(name="Broken Equip", status=EquipmentStatus.broken)

        result = create_equipment(body, db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.status == EquipmentStatus.broken

    def test_creates_api_controllable_equipment(self):
        db = MagicMock()
        body = EquipmentCreate(
            name="Robot Arm",
            is_api_controllable=True,
            api_interface="http",
        )

        result = create_equipment(body, db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.is_api_controllable is True
        assert added_obj.api_interface == "http"

    def test_creates_with_photos(self):
        db = MagicMock()
        body = EquipmentCreate(
            name="Photo Equip",
            photos=["/img/front.jpg", "/img/back.jpg"],
        )

        result = create_equipment(body, db)

        added_obj = db.add.call_args[0][0]
        assert len(added_obj.photos) == 2

    def test_creates_with_extracted_data(self):
        db = MagicMock()
        body = EquipmentCreate(
            name="Extracted Equip",
            extracted_data={"source_model": "gemini-3.1-flash-preview"},
        )

        result = create_equipment(body, db)

        added_obj = db.add.call_args[0][0]
        assert added_obj.extracted_data["source_model"] == "gemini-3.1-flash-preview"


# ---------------------------------------------------------------------------
# get_equipment handler
# ---------------------------------------------------------------------------


class TestGetEquipment:
    """Tests for the get_equipment route handler."""

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_returns_equipment_by_id(self, mock_get):
        db = MagicMock()
        expected = _make_equipment(id=42, name="Found It")
        mock_get.return_value = expected

        result = get_equipment(42, db)

        mock_get.assert_called_once_with(db, Equipment, 42, "Equipment")
        assert result is expected

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_raises_not_found_for_missing_id(self, mock_get):
        db = MagicMock()
        mock_get.side_effect = NotFoundError("Equipment", 99999)

        with pytest.raises(NotFoundError):
            get_equipment(99999, db)


# ---------------------------------------------------------------------------
# update_equipment handler
# ---------------------------------------------------------------------------


class TestUpdateEquipment:
    """Tests for the update_equipment route handler."""

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_name(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, name="Old Name")
        mock_get.return_value = equip

        body = EquipmentUpdate(name="New Name")
        result = update_equipment(1, body, db)

        assert equip.name == "New Name"
        db.flush.assert_called_once()
        db.refresh.assert_called_once()

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_status_to_broken(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, status=EquipmentStatus.active)
        mock_get.return_value = equip

        body = EquipmentUpdate(status=EquipmentStatus.broken)
        update_equipment(1, body, db)

        assert equip.status == EquipmentStatus.broken

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_status_to_maintenance(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, status=EquipmentStatus.active)
        mock_get.return_value = equip

        body = EquipmentUpdate(status=EquipmentStatus.maintenance)
        update_equipment(1, body, db)

        assert equip.status == EquipmentStatus.maintenance

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_status_to_retired(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, status=EquipmentStatus.active)
        mock_get.return_value = equip

        body = EquipmentUpdate(status=EquipmentStatus.retired)
        update_equipment(1, body, db)

        assert equip.status == EquipmentStatus.retired

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_status_to_decommissioned(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, status=EquipmentStatus.active)
        mock_get.return_value = equip

        body = EquipmentUpdate(status=EquipmentStatus.decommissioned)
        update_equipment(1, body, db)

        assert equip.status == EquipmentStatus.decommissioned

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_multiple_fields(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1)
        mock_get.return_value = equip

        body = EquipmentUpdate(
            name="Updated Name",
            manufacturer="New Mfr",
            room="Room 202",
            estimated_value=Decimal("10000"),
        )
        update_equipment(1, body, db)

        assert equip.name == "Updated Name"
        assert equip.manufacturer == "New Mfr"
        assert equip.room == "Room 202"
        assert equip.estimated_value == Decimal("10000")

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_only_provided_fields(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, name="Original", manufacturer="Orig Mfr")
        mock_get.return_value = equip

        body = EquipmentUpdate(name="Changed")
        update_equipment(1, body, db)

        assert equip.name == "Changed"
        # manufacturer should NOT be overwritten since it was not in the update
        assert equip.manufacturer == "Orig Mfr"

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_photos(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, photos=[])
        mock_get.return_value = equip

        body = EquipmentUpdate(photos=["/img/new.jpg"])
        update_equipment(1, body, db)

        assert equip.photos == ["/img/new.jpg"]

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_api_controllable(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, is_api_controllable=False)
        mock_get.return_value = equip

        body = EquipmentUpdate(is_api_controllable=True, api_interface="tcp")
        update_equipment(1, body, db)

        assert equip.is_api_controllable is True
        assert equip.api_interface == "tcp"

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_raises_not_found(self, mock_get):
        db = MagicMock()
        mock_get.side_effect = NotFoundError("Equipment", 999)

        body = EquipmentUpdate(name="Nope")
        with pytest.raises(NotFoundError):
            update_equipment(999, body, db)


# ---------------------------------------------------------------------------
# delete_equipment handler (soft delete)
# ---------------------------------------------------------------------------


class TestDeleteEquipment:
    """Tests for the delete_equipment route handler (soft delete)."""

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_soft_delete_sets_status_to_deleted(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, status=EquipmentStatus.active)
        mock_get.return_value = equip

        result = delete_equipment(1, db)

        assert equip.status == EquipmentStatus.deleted
        db.flush.assert_called_once()
        assert result is None

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_delete_already_broken_equipment(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, status=EquipmentStatus.broken)
        mock_get.return_value = equip

        delete_equipment(1, db)

        assert equip.status == EquipmentStatus.deleted

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_delete_raises_not_found(self, mock_get):
        db = MagicMock()
        mock_get.side_effect = NotFoundError("Equipment", 999)

        with pytest.raises(NotFoundError):
            delete_equipment(999, db)


# ---------------------------------------------------------------------------
# list_equipment handler
# ---------------------------------------------------------------------------



class TestEquipmentStatusConstants:
    """Tests for status constants and valid status set."""

    def test_all_status_values(self):
        assert EquipmentStatus.active == "active"
        assert EquipmentStatus.maintenance == "maintenance"
        assert EquipmentStatus.broken == "broken"
        assert EquipmentStatus.retired == "retired"
        assert EquipmentStatus.decommissioned == "decommissioned"
        assert EquipmentStatus.deleted == "deleted"

    def test_valid_statuses_contains_all(self):
        assert len(_VALID_EQUIPMENT_STATUSES) == 6
        assert EquipmentStatus.active in _VALID_EQUIPMENT_STATUSES
        assert EquipmentStatus.maintenance in _VALID_EQUIPMENT_STATUSES
        assert EquipmentStatus.broken in _VALID_EQUIPMENT_STATUSES
        assert EquipmentStatus.retired in _VALID_EQUIPMENT_STATUSES
        assert EquipmentStatus.decommissioned in _VALID_EQUIPMENT_STATUSES
        assert EquipmentStatus.deleted in _VALID_EQUIPMENT_STATUSES

    def test_sortable_columns(self):
        assert _SORTABLE == {
            "id",
            "created_at",
            "updated_at",
            "name",
            "manufacturer",
            "category",
            "status",
        }


# ---------------------------------------------------------------------------
# Status transition scenarios
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    """Tests for status transition workflows via update handler."""

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_active_to_maintenance(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(status=EquipmentStatus.active)
        mock_get.return_value = equip

        update_equipment(1, EquipmentUpdate(status=EquipmentStatus.maintenance), db)
        assert equip.status == EquipmentStatus.maintenance

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_maintenance_to_active(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(status=EquipmentStatus.maintenance)
        mock_get.return_value = equip

        update_equipment(1, EquipmentUpdate(status=EquipmentStatus.active), db)
        assert equip.status == EquipmentStatus.active

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_active_to_broken(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(status=EquipmentStatus.active)
        mock_get.return_value = equip

        update_equipment(1, EquipmentUpdate(status=EquipmentStatus.broken), db)
        assert equip.status == EquipmentStatus.broken

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_broken_to_maintenance(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(status=EquipmentStatus.broken)
        mock_get.return_value = equip

        update_equipment(1, EquipmentUpdate(status=EquipmentStatus.maintenance), db)
        assert equip.status == EquipmentStatus.maintenance

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_broken_to_retired(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(status=EquipmentStatus.broken)
        mock_get.return_value = equip

        update_equipment(1, EquipmentUpdate(status=EquipmentStatus.retired), db)
        assert equip.status == EquipmentStatus.retired

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_retired_to_decommissioned(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(status=EquipmentStatus.retired)
        mock_get.return_value = equip

        update_equipment(1, EquipmentUpdate(status=EquipmentStatus.decommissioned), db)
        assert equip.status == EquipmentStatus.decommissioned

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_any_status_to_deleted_via_soft_delete(self, mock_get):
        db = MagicMock()
        for initial_status in [
            EquipmentStatus.active,
            EquipmentStatus.broken,
            EquipmentStatus.maintenance,
            EquipmentStatus.retired,
            EquipmentStatus.decommissioned,
        ]:
            equip = _make_equipment(status=initial_status)
            mock_get.return_value = equip
            db.reset_mock()

            delete_equipment(1, db)
            assert equip.status == EquipmentStatus.deleted


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_create_body_dump_matches_model_fields(self):
        body = EquipmentCreate(
            name="Test",
            manufacturer="Mfr",
            category="cat",
            estimated_value=Decimal("1000"),
        )
        dumped = body.model_dump()
        assert dumped["name"] == "Test"
        assert dumped["manufacturer"] == "Mfr"
        assert dumped["category"] == "cat"
        assert dumped["estimated_value"] == Decimal("1000")
        assert dumped["status"] == EquipmentStatus.active

    def test_update_body_exclude_unset_excludes_none(self):
        body = EquipmentUpdate(name="OnlyName")
        dumped = body.model_dump(exclude_unset=True)
        assert set(dumped.keys()) == {"name"}

    def test_update_body_exclude_unset_includes_status_change(self):
        body = EquipmentUpdate(status=EquipmentStatus.broken)
        dumped = body.model_dump(exclude_unset=True)
        assert dumped == {"status": EquipmentStatus.broken}

    def test_create_with_zero_value(self):
        body = EquipmentCreate(name="Free Equip", estimated_value=Decimal("0"))
        assert body.estimated_value == Decimal("0")

    def test_create_with_large_value(self):
        body = EquipmentCreate(
            name="Expensive", estimated_value=Decimal("9999999999.99")
        )
        assert body.estimated_value == Decimal("9999999999.99")

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_clears_optional_string_to_none(self, mock_get):
        """Setting an optional string field to None should clear it."""
        db = MagicMock()
        equip = _make_equipment(id=1, manufacturer="Existing")
        mock_get.return_value = equip

        body = EquipmentUpdate(manufacturer=None)
        dumped = body.model_dump(exclude_unset=True)
        # None is explicitly set, so it should be in the dump
        assert "manufacturer" in dumped
        assert dumped["manufacturer"] is None

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_with_extra_dict(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, extra={})
        mock_get.return_value = equip

        body = EquipmentUpdate(extra={"warranty": "2027-01-01"})
        update_equipment(1, body, db)
        assert equip.extra == {"warranty": "2027-01-01"}

    @patch("lab_manager.api.routes.equipment.get_or_404")
    def test_update_with_extracted_data(self, mock_get):
        db = MagicMock()
        equip = _make_equipment(id=1, extracted_data=None)
        mock_get.return_value = equip

        extracted = {
            "source_model": "gemini-3.1-pro-preview",
            "confidence": 0.92,
            "fields": {"serial": "SN-X100"},
        }
        body = EquipmentUpdate(extracted_data=extracted)
        update_equipment(1, body, db)
        assert equip.extracted_data["confidence"] == 0.92

    def test_create_default_is_api_controllable_false(self):
        body = EquipmentCreate(name="Manual Equip")
        assert body.is_api_controllable is False

    def test_create_default_api_interface_none(self):
        body = EquipmentCreate(name="No API")
        assert body.api_interface is None

    def test_create_default_location_id_none(self):
        body = EquipmentCreate(name="No Location")
        assert body.location_id is None

    def test_create_with_location_id(self):
        body = EquipmentCreate(name="Located Equip", location_id=42)
        assert body.location_id == 42
