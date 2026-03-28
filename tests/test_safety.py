"""Unit tests for the safety service — GHS hazard mapping, PPE, disposal, inventory scan."""

from __future__ import annotations


from lab_manager.models.product import Product
from lab_manager.services.safety import (
    GHS_HAZARD_MAP,
    _parse_hazard_codes,
    check_inventory_safety,
    get_product_safety_info,
    get_ppe_requirements,
    get_waste_disposal_guide,
)


# ---------------------------------------------------------------------------
# GHS Hazard Mapping
# ---------------------------------------------------------------------------


class TestGHSHazardMap:
    """Test the GHS_HAZARD_MAP data structure."""

    def test_map_has_entries(self):
        assert len(GHS_HAZARD_MAP) > 0

    def test_each_entry_has_required_keys(self):
        for code, entry in GHS_HAZARD_MAP.items():
            assert "category" in entry, f"{code} missing 'category'"
            assert "ppe" in entry, f"{code} missing 'ppe'"
            assert "disposal" in entry, f"{code} missing 'disposal'"

    def test_each_entry_values_are_nonempty(self):
        for code, entry in GHS_HAZARD_MAP.items():
            assert entry["category"], f"{code} has empty category"
            assert entry["ppe"], f"{code} has empty ppe"
            assert entry["disposal"], f"{code} has empty disposal"

    def test_physical_hazards_present(self):
        """H200-H299 range (explosive, flammable, etc.) has entries."""
        physical_codes = [c for c in GHS_HAZARD_MAP if c.startswith("H2")]
        assert len(physical_codes) >= 5, "Expected >=5 physical hazard entries"

    def test_health_hazards_present(self):
        """H300-H399 range has entries."""
        health_codes = [c for c in GHS_HAZARD_MAP if c.startswith("H3")]
        assert len(health_codes) >= 5, "Expected >=5 health hazard entries"

    def test_environmental_hazards_present(self):
        """H400-H499 range has entries."""
        env_codes = [c for c in GHS_HAZARD_MAP if c.startswith("H4")]
        assert len(env_codes) >= 3, "Expected >=3 environmental hazard entries"


# ---------------------------------------------------------------------------
# Hazard Code Parsing
# ---------------------------------------------------------------------------


class TestParseHazardCodes:
    def test_single_code(self):
        assert _parse_hazard_codes("H225") == ["H225"]

    def test_multiple_codes(self):
        assert _parse_hazard_codes("H225 H314 H331") == ["H225", "H314", "H331"]

    def test_code_in_sentence(self):
        result = _parse_hazard_codes("H225 Highly flammable liquid and vapour")
        assert result == ["H225"]

    def test_mixed_case(self):
        result = _parse_hazard_codes("h225 h314")
        assert result == ["H225", "H314"]

    def test_empty_string(self):
        assert _parse_hazard_codes("") == []

    def test_none(self):
        assert _parse_hazard_codes(None) == []

    def test_euh_code(self):
        result = _parse_hazard_codes("EUH071")
        assert result == ["EUH071"]

    def test_no_codes_found(self):
        assert _parse_hazard_codes("just some text without codes") == []


# ---------------------------------------------------------------------------
# PPE Requirements
# ---------------------------------------------------------------------------


class TestPPERequirements:
    def test_flammable_chemical(self):
        result = get_ppe_requirements("H225")
        assert "Use in fume hood" in result
        assert "no open flames" in result
        assert "fire-resistant lab coat" in result
        assert "safety goggles" in result

    def test_corrosive_chemical(self):
        result = get_ppe_requirements("H314")
        assert "Acid-resistant gloves" in result
        assert "face shield" in result
        assert "chemical apron" in result

    def test_acute_toxic(self):
        result = get_ppe_requirements("H300")
        assert "fume hood" in " ".join(result).lower()
        assert any("face shield" in item for item in result)

    def test_inhalation_hazard(self):
        result = get_ppe_requirements("H331")
        assert "fume hood" in " ".join(result).lower()

    def test_environmental(self):
        result = get_ppe_requirements("H400")
        assert len(result) > 0

    def test_unknown_code_returns_sds_guidance(self):
        result = get_ppe_requirements("H999")
        assert len(result) == 1
        assert "SDS" in result[0]

    def test_case_insensitive(self):
        result_lower = get_ppe_requirements("h225")
        result_upper = get_ppe_requirements("H225")
        assert result_lower == result_upper

    def test_whitespace_stripped(self):
        result = get_ppe_requirements("  H225  ")
        assert "Use in fume hood" in result

    def test_returns_list(self):
        result = get_ppe_requirements("H225")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)


# ---------------------------------------------------------------------------
# Waste Disposal Guide
# ---------------------------------------------------------------------------


class TestWasteDisposalGuide:
    def test_flammable_disposal(self):
        result = get_waste_disposal_guide("H225")
        assert "flammable" in result.lower()
        assert "waste" in result.lower()

    def test_corrosive_disposal(self):
        result = get_waste_disposal_guide("H314")
        assert "neutralize" in result.lower() or "neutralise" in result.lower()

    def test_environmental_disposal(self):
        result = get_waste_disposal_guide("H400")
        assert "drains" in result.lower()
        assert "separately" in result.lower()

    def test_unknown_code_returns_generic(self):
        result = get_waste_disposal_guide("H999")
        assert "institutional" in result.lower() or "procedures" in result.lower()

    def test_returns_string(self):
        result = get_waste_disposal_guide("H225")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_carcinogen_disposal(self):
        result = get_waste_disposal_guide("H350")
        assert "carcinogen" in result.lower()


# ---------------------------------------------------------------------------
# Product Safety Info
# ---------------------------------------------------------------------------


class TestProductSafetyInfo:
    def test_product_with_single_hazard(self):
        product = Product(
            id=1,
            name="Test Chemical",
            catalog_number="TEST-001",
            hazard_info="H225",
            is_hazardous=True,
        )
        result = get_product_safety_info(product)
        assert result["product_id"] == 1
        assert result["product_name"] == "Test Chemical"
        assert result["is_hazardous"] is True
        assert result["hazard_codes"] == ["H225"]
        assert len(result["ppe_requirements"]) > 0
        assert len(result["waste_disposal"]) > 0

    def test_product_with_multiple_hazards(self):
        product = Product(
            id=2,
            name="Multi Hazard",
            catalog_number="MH-001",
            hazard_info="H225 H314 H400",
            is_hazardous=True,
        )
        result = get_product_safety_info(product)
        assert result["hazard_codes"] == ["H225", "H314", "H400"]
        # Should have PPE from all three codes
        assert len(result["ppe_requirements"]) >= 3
        assert len(result["waste_disposal"]) >= 3

    def test_product_no_hazard_info(self):
        product = Product(
            id=3,
            name="Safe Chemical",
            catalog_number="SAFE-001",
            hazard_info=None,
            is_hazardous=False,
        )
        result = get_product_safety_info(product)
        assert result["hazard_codes"] == []
        assert result["ppe_requirements"] == []
        assert result["waste_disposal"] == []
        assert result["is_hazardous"] is False

    def test_deduplication_of_ppe(self):
        """Multiple codes with overlapping PPE should not duplicate."""
        product = Product(
            id=4,
            name="Duplicate PPE",
            catalog_number="DUP-001",
            hazard_info="H302 H312",  # Both have "Wear nitrile gloves"
            is_hazardous=True,
        )
        result = get_product_safety_info(product)
        ppe = result["ppe_requirements"]
        # Count occurrences of "Wear nitrile gloves"
        glove_count = sum(1 for p in ppe if "nitrile gloves" in p.lower())
        assert glove_count == 1, f"Expected 1 glove entry, got {glove_count}: {ppe}"


# ---------------------------------------------------------------------------
# Inventory Safety Scan (unit-level with mock-like DB)
# ---------------------------------------------------------------------------


class TestInventorySafetyScan:
    def test_hazardous_without_hazard_info(self, db_session):
        """Products marked hazardous but missing hazard_info generate a warning."""
        p = Product(
            catalog_number="NOH-001",
            name="Missing Info Chemical",
            is_hazardous=True,
            hazard_info=None,
            cas_number="1234-56-7",
        )
        db_session.add(p)
        db_session.flush()

        warnings = check_inventory_safety(db_session)
        assert len(warnings) >= 1
        assert any(w["warning_type"] == "missing_hazard_info" for w in warnings)

    def test_hazardous_without_cas(self, db_session):
        """Products marked hazardous but missing CAS number generate a warning."""
        p = Product(
            catalog_number="NOC-001",
            name="No CAS Chemical",
            is_hazardous=True,
            hazard_info="H225",
            cas_number=None,
        )
        db_session.add(p)
        db_session.flush()

        warnings = check_inventory_safety(db_session)
        assert any(w["warning_type"] == "missing_cas_number" for w in warnings)

    def test_non_hazardous_products_not_flagged(self, db_session):
        """Non-hazardous products should not generate warnings."""
        p = Product(
            catalog_number="SAFE-002",
            name="Safe Chemical",
            is_hazardous=False,
        )
        db_session.add(p)
        db_session.flush()

        warnings = check_inventory_safety(db_session)
        product_warnings = [
            w for w in warnings if w.get("product_name") == "Safe Chemical"
        ]
        assert len(product_warnings) == 0

    def test_unrecognized_hazard_codes(self, db_session):
        """Hazardous products with hazard_info but no H-codes get flagged."""
        p = Product(
            catalog_number="BAD-001",
            name="Bad Codes Chemical",
            is_hazardous=True,
            hazard_info="Corrosive and toxic",
            cas_number="5678-90-1",
        )
        db_session.add(p)
        db_session.flush()

        warnings = check_inventory_safety(db_session)
        assert any(w["warning_type"] == "unrecognized_hazard_codes" for w in warnings)

    def test_fully_documented_product_no_warning(self, db_session):
        """A product with hazard_info, CAS, and valid H-codes should not be flagged."""
        p = Product(
            catalog_number="GOOD-001",
            name="Well Documented Chemical",
            is_hazardous=True,
            hazard_info="H225 H314",
            cas_number="9999-99-9",
        )
        db_session.add(p)
        db_session.flush()

        warnings = check_inventory_safety(db_session)
        product_warnings = [
            w for w in warnings if w.get("product_name") == "Well Documented Chemical"
        ]
        assert len(product_warnings) == 0

    def test_warning_has_required_fields(self, db_session):
        """Each warning dict has the expected keys."""
        p = Product(
            catalog_number="FIELD-001",
            name="Field Test Chemical",
            is_hazardous=True,
            hazard_info=None,
        )
        db_session.add(p)
        db_session.flush()

        warnings = check_inventory_safety(db_session)
        matching = [w for w in warnings if w["product_name"] == "Field Test Chemical"]
        assert len(matching) >= 1
        for w in matching:
            assert "product_id" in w
            assert "product_name" in w
            assert "catalog_number" in w
            assert "warning_type" in w
            assert "severity" in w
            assert "message" in w
