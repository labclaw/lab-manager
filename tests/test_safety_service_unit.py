"""Unit tests for safety service — GHS hazard code parsing, PPE, disposal, and inventory checks."""

from types import SimpleNamespace
from unittest.mock import MagicMock


from lab_manager.services.safety import (
    GHS_HAZARD_MAP,
    _parse_hazard_codes,
    get_ppe_requirements,
    get_waste_disposal_guide,
    get_product_safety_info,
    check_inventory_safety,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_product(
    id=1,
    name="TestChem",
    catalog_number="CAT-001",
    hazard_info="",
    is_hazardous=False,
    cas_number=None,
):
    """Create a lightweight mock Product object."""
    return SimpleNamespace(
        id=id,
        name=name,
        catalog_number=catalog_number,
        hazard_info=hazard_info,
        is_hazardous=is_hazardous,
        cas_number=cas_number,
    )


# ===================================================================
# _parse_hazard_codes
# ===================================================================


class TestParseHazardCodesEmptyAndNone:
    """Edge cases for empty / None input."""

    def test_empty_string(self):
        assert _parse_hazard_codes("") == []

    def test_none_input(self):
        assert _parse_hazard_codes(None) == []

    def test_whitespace_only(self):
        assert _parse_hazard_codes("   ") == []


class TestParseHazardCodesSingleCode:
    """Single code extraction."""

    def test_single_h_code(self):
        assert _parse_hazard_codes("H225") == ["H225"]

    def test_single_euh_code(self):
        assert _parse_hazard_codes("EUH071") == ["EUH071"]

    def test_code_at_start_of_text(self):
        assert _parse_hazard_codes("H225 Highly flammable liquid") == ["H225"]

    def test_code_at_end_of_text(self):
        assert _parse_hazard_codes("Flammable H225") == ["H225"]

    def test_code_in_middle_of_text(self):
        assert _parse_hazard_codes("Causes H314 skin burns") == ["H314"]


class TestParseHazardCodesMultipleCodes:
    """Multiple codes in one string."""

    def test_two_codes_comma_separated(self):
        result = _parse_hazard_codes("H225, H314")
        assert result == ["H225", "H314"]

    def test_three_codes_space_separated(self):
        result = _parse_hazard_codes("H225 H314 H350")
        assert result == ["H225", "H314", "H350"]

    def test_codes_mixed_with_text(self):
        result = _parse_hazard_codes(
            "H225 Highly flammable, H314 causes burns, H350 may cause cancer"
        )
        assert result == ["H225", "H314", "H350"]

    def test_codes_with_semicolons(self):
        result = _parse_hazard_codes("H225; H314; H350")
        assert result == ["H225", "H314", "H350"]


class TestParseHazardCodesMixedCase:
    """Case-insensitive parsing — results always uppercased."""

    def test_lowercase_code(self):
        assert _parse_hazard_codes("h225") == ["H225"]

    def test_mixed_case_code(self):
        assert _parse_hazard_codes("H225") == ["H225"]

    def test_all_lowercase(self):
        assert _parse_hazard_codes("h314 h350") == ["H314", "H350"]

    def test_euh_lowercase(self):
        assert _parse_hazard_codes("euh071") == ["EUH071"]

    def test_euh_mixed_case(self):
        assert _parse_hazard_codes("Euh071") == ["EUH071"]


class TestParseHazardCodesNonCodeText:
    """Free text without valid codes."""

    def test_plain_english(self):
        assert _parse_hazard_codes("flammable liquid, toxic") == []

    def test_partial_h_code_no_match(self):
        assert _parse_hazard_codes("H22") == []

    def test_h_with_four_digits_no_match(self):
        assert _parse_hazard_codes("H2250") == []

    def test_number_without_h_prefix(self):
        assert _parse_hazard_codes("225") == []

    def test_empty_parentheses(self):
        assert _parse_hazard_codes("()") == []


class TestParseHazardCodesEUHCodes:
    """EUH-specific hazard statement codes."""

    def test_euh071(self):
        assert _parse_hazard_codes("EUH071") == ["EUH071"]

    def test_euh_in_context(self):
        result = _parse_hazard_codes("Corrosive to respiratory tract EUH071")
        assert result == ["EUH071"]

    def test_euh_with_h_codes(self):
        result = _parse_hazard_codes("H314 EUH071 H225")
        assert result == ["H314", "EUH071", "H225"]


# ===================================================================
# get_ppe_requirements
# ===================================================================


class TestPpeRequirementsKnownCodes:
    """Known hazard codes return specific PPE items."""

    def test_h225_items(self):
        ppe = get_ppe_requirements("H225")
        assert "safety goggles" in ppe
        assert "fire-resistant lab coat" in ppe

    def test_h314_items(self):
        ppe = get_ppe_requirements("H314")
        assert "Acid-resistant gloves" in ppe
        assert "face shield" in ppe

    def test_h350_items(self):
        ppe = get_ppe_requirements("H350")
        assert "chemical apron" in ppe
        assert "double gloves" in ppe

    def test_h300_items(self):
        ppe = get_ppe_requirements("H300")
        assert "double gloves" in ppe
        assert "chemical apron" in ppe

    def test_h400_items(self):
        ppe = get_ppe_requirements("H400")
        assert "Wear nitrile gloves" in ppe


class TestPpeRequirementsUnknownCode:
    """Unknown codes return the default SDS consultation message."""

    def test_unknown_code(self):
        result = get_ppe_requirements("H999")
        assert result == ["Consult SDS for detailed PPE requirements"]

    def test_completely_fake_code(self):
        result = get_ppe_requirements("ZZZZZ")
        assert result == ["Consult SDS for detailed PPE requirements"]

    def test_empty_string_code(self):
        result = get_ppe_requirements("")
        assert result == ["Consult SDS for detailed PPE requirements"]


class TestPpeRequirementsCaseAndWhitespace:
    """Case normalization and whitespace stripping."""

    def test_lowercase_input(self):
        ppe = get_ppe_requirements("h225")
        assert "safety goggles" in ppe

    def test_leading_trailing_whitespace(self):
        ppe = get_ppe_requirements("  H225  ")
        assert "safety goggles" in ppe

    def test_mixed_case_whitespace(self):
        ppe = get_ppe_requirements("  h314 ")
        assert "Acid-resistant gloves" in ppe

    def test_tab_characters(self):
        ppe = get_ppe_requirements("\tH225\t")
        assert "safety goggles" in ppe


class TestPpeRequirementsReturnsList:
    """Return type and structure checks."""

    def test_returns_list(self):
        assert isinstance(get_ppe_requirements("H225"), list)

    def test_items_are_strings(self):
        for item in get_ppe_requirements("H225"):
            assert isinstance(item, str)

    def test_items_are_stripped(self):
        """Each PPE item should have no leading/trailing whitespace."""
        for item in get_ppe_requirements("H225"):
            assert item == item.strip()


# ===================================================================
# get_waste_disposal_guide
# ===================================================================


class TestWasteDisposalKnownCodes:
    """Known codes return specific disposal instructions."""

    def test_h225_disposal(self):
        result = get_waste_disposal_guide("H225")
        assert "flammable waste container" in result

    def test_h314_disposal(self):
        result = get_waste_disposal_guide("H314")
        assert "Neutralize" in result

    def test_h350_disposal(self):
        result = get_waste_disposal_guide("H350")
        assert "carcinogen" in result

    def test_h400_disposal(self):
        result = get_waste_disposal_guide("H400")
        assert "drains" in result

    def test_h200_disposal(self):
        result = get_waste_disposal_guide("H200")
        assert "EHS" in result

    def test_h240_disposal(self):
        result = get_waste_disposal_guide("H240")
        assert "EHS" in result

    def test_euh071_disposal(self):
        result = get_waste_disposal_guide("EUH071")
        assert "hazardous chemical waste" in result


class TestWasteDisposalUnknownCode:
    """Unknown codes return the default disposal message."""

    def test_unknown_code(self):
        result = get_waste_disposal_guide("H999")
        assert result == "Follow institutional chemical waste disposal procedures."

    def test_completely_fake_code(self):
        result = get_waste_disposal_guide("XXXXX")
        assert result == "Follow institutional chemical waste disposal procedures."

    def test_empty_string(self):
        result = get_waste_disposal_guide("")
        assert result == "Follow institutional chemical waste disposal procedures."


class TestWasteDisposalCaseNormalization:
    """Case normalization in disposal lookups."""

    def test_lowercase(self):
        result = get_waste_disposal_guide("h225")
        assert "flammable waste container" in result

    def test_whitespace(self):
        result = get_waste_disposal_guide("  H225 ")
        assert "flammable waste container" in result


class TestWasteDisposalReturnTypes:
    """Return type checks."""

    def test_returns_string(self):
        assert isinstance(get_waste_disposal_guide("H225"), str)

    def test_unknown_returns_string(self):
        assert isinstance(get_waste_disposal_guide("H999"), str)


# ===================================================================
# get_product_safety_info
# ===================================================================


class TestProductSafetyInfoBasicFields:
    """Basic field mapping from Product to output dict."""

    def test_product_id_mapped(self):
        p = _make_product(id=42, hazard_info="H225")
        info = get_product_safety_info(p)
        assert info["product_id"] == 42

    def test_product_name_mapped(self):
        p = _make_product(name="Acetone", hazard_info="H225")
        info = get_product_safety_info(p)
        assert info["product_name"] == "Acetone"

    def test_is_hazardous_true(self):
        p = _make_product(is_hazardous=True, hazard_info="H225")
        info = get_product_safety_info(p)
        assert info["is_hazardous"] is True

    def test_is_hazardous_false(self):
        p = _make_product(is_hazardous=False, hazard_info="H225")
        info = get_product_safety_info(p)
        assert info["is_hazardous"] is False


class TestProductSafetyInfoHazardCodes:
    """Hazard code extraction from product."""

    def test_single_code_extracted(self):
        p = _make_product(hazard_info="H225")
        info = get_product_safety_info(p)
        assert info["hazard_codes"] == ["H225"]

    def test_multiple_codes_extracted(self):
        p = _make_product(hazard_info="H225, H314, H350")
        info = get_product_safety_info(p)
        assert info["hazard_codes"] == ["H225", "H314", "H350"]

    def test_empty_hazard_info(self):
        p = _make_product(hazard_info="")
        info = get_product_safety_info(p)
        assert info["hazard_codes"] == []

    def test_none_hazard_info(self):
        p = _make_product(hazard_info=None)
        info = get_product_safety_info(p)
        assert info["hazard_codes"] == []


class TestProductSafetyInfoPpeAggregation:
    """PPE requirements aggregated from multiple codes."""

    def test_single_code_ppe(self):
        p = _make_product(hazard_info="H225")
        info = get_product_safety_info(p)
        assert "safety goggles" in info["ppe_requirements"]

    def test_multiple_codes_ppe_aggregated(self):
        p = _make_product(hazard_info="H225 H314")
        info = get_product_safety_info(p)
        # H225 PPE includes "safety goggles"
        assert "safety goggles" in info["ppe_requirements"]
        # H314 PPE includes "Acid-resistant gloves"
        assert "Acid-resistant gloves" in info["ppe_requirements"]

    def test_deduplication_of_ppe(self):
        """Two codes that share a PPE item should not duplicate it."""
        # Both H225 and H226 have "Use in fume hood"
        p = _make_product(hazard_info="H225 H226")
        info = get_product_safety_info(p)
        fume_hood_count = info["ppe_requirements"].count("Use in fume hood")
        assert fume_hood_count == 1

    def test_empty_hazard_info_no_ppe(self):
        p = _make_product(hazard_info="")
        info = get_product_safety_info(p)
        assert info["ppe_requirements"] == []


class TestProductSafetyInfoDisposalAggregation:
    """Waste disposal aggregated from multiple codes."""

    def test_single_code_disposal(self):
        p = _make_product(hazard_info="H225")
        info = get_product_safety_info(p)
        assert len(info["waste_disposal"]) == 1
        assert "flammable waste container" in info["waste_disposal"][0]

    def test_multiple_codes_disposal_aggregated(self):
        p = _make_product(hazard_info="H225 H314")
        info = get_product_safety_info(p)
        assert len(info["waste_disposal"]) == 2

    def test_deduplication_of_disposal(self):
        """Two codes with the same disposal text should not duplicate."""
        # H400 and H401 have identical disposal strings
        p = _make_product(hazard_info="H400 H401")
        info = get_product_safety_info(p)
        assert len(info["waste_disposal"]) == 1

    def test_empty_hazard_info_no_disposal(self):
        p = _make_product(hazard_info="")
        info = get_product_safety_info(p)
        assert info["waste_disposal"] == []


class TestProductSafetyInfoOutputKeys:
    """Verify all expected keys are present in the output dict."""

    def test_all_keys_present(self):
        p = _make_product(hazard_info="H225")
        info = get_product_safety_info(p)
        expected_keys = {
            "product_id",
            "product_name",
            "is_hazardous",
            "hazard_codes",
            "ppe_requirements",
            "waste_disposal",
        }
        assert set(info.keys()) == expected_keys


# ===================================================================
# check_inventory_safety
# ===================================================================


def _mock_db(products_by_query):
    """Build a mock DB session.

    ``products_by_query`` is a list of lists. Each call to ``db.scalars(...)``
    returns the next list of products. This lets us control what each of the
    three queries inside ``check_inventory_safety`` returns.
    """
    db = MagicMock()
    call_idx = [0]

    def scalars_side_effect(stmt):
        idx = call_idx[0]
        call_idx[0] += 1
        if idx < len(products_by_query):
            result_mock = MagicMock()
            result_mock.all.return_value = products_by_query[idx]
            return result_mock
        result_mock = MagicMock()
        result_mock.all.return_value = []
        return result_mock

    db.scalars.side_effect = scalars_side_effect
    return db


class TestCheckInventorySafetyMissingHazardInfo:
    """Hazardous products with missing hazard_info trigger warnings."""

    def test_missing_hazard_info_none(self):
        p = _make_product(id=1, name="DangerChem", is_hazardous=True, hazard_info=None)
        db = _mock_db([[p], [], []])
        warnings = check_inventory_safety(db)
        assert len(warnings) == 1
        assert warnings[0]["warning_type"] == "missing_hazard_info"
        assert warnings[0]["severity"] == "warning"
        assert "DangerChem" in warnings[0]["message"]

    def test_missing_hazard_info_empty(self):
        p = _make_product(id=2, name="BadChem", is_hazardous=True, hazard_info="")
        db = _mock_db([[p], [], []])
        warnings = check_inventory_safety(db)
        assert len(warnings) == 1
        assert warnings[0]["warning_type"] == "missing_hazard_info"

    def test_multiple_missing_hazard_info(self):
        p1 = _make_product(id=1, name="ChemA", is_hazardous=True, hazard_info=None)
        p2 = _make_product(id=2, name="ChemB", is_hazardous=True, hazard_info="")
        db = _mock_db([[p1, p2], [], []])
        warnings = check_inventory_safety(db)
        missing = [w for w in warnings if w["warning_type"] == "missing_hazard_info"]
        assert len(missing) == 2


class TestCheckInventorySafetyMissingCasNumber:
    """Hazardous products missing CAS numbers trigger info warnings."""

    def test_missing_cas_none(self):
        p = _make_product(
            id=3, name="NoCAS", is_hazardous=True, hazard_info="H225", cas_number=None
        )
        db = _mock_db([[], [p], [p]])
        warnings = check_inventory_safety(db)
        cas_warnings = [
            w for w in warnings if w["warning_type"] == "missing_cas_number"
        ]
        assert len(cas_warnings) == 1
        assert cas_warnings[0]["severity"] == "info"
        assert "CAS number" in cas_warnings[0]["message"]

    def test_missing_cas_empty(self):
        p = _make_product(
            id=4, name="EmptyCAS", is_hazardous=True, hazard_info="H225", cas_number=""
        )
        db = _mock_db([[], [p], [p]])
        warnings = check_inventory_safety(db)
        cas_warnings = [
            w for w in warnings if w["warning_type"] == "missing_cas_number"
        ]
        assert len(cas_warnings) == 1

    def test_cas_present_no_warning(self):
        p = _make_product(
            id=5,
            name="WithCAS",
            is_hazardous=True,
            hazard_info="H225",
            cas_number="67-64-1",
        )
        db = _mock_db([[], [], [p]])
        warnings = check_inventory_safety(db)
        cas_warnings = [
            w for w in warnings if w["warning_type"] == "missing_cas_number"
        ]
        assert len(cas_warnings) == 0


class TestCheckInventorySafetyUnrecognizedCodes:
    """Products with hazard_info but no recognizable GHS codes."""

    def test_unrecognized_free_text(self):
        p = _make_product(
            id=6, name="WeirdInfo", is_hazardous=True, hazard_info="very toxic stuff"
        )
        db = _mock_db([[], [], [p]])
        warnings = check_inventory_safety(db)
        unrecognized = [
            w for w in warnings if w["warning_type"] == "unrecognized_hazard_codes"
        ]
        assert len(unrecognized) == 1
        assert unrecognized[0]["severity"] == "info"
        assert "recognized GHS codes" in unrecognized[0]["message"]

    def test_valid_codes_no_warning(self):
        p = _make_product(
            id=7, name="GoodInfo", is_hazardous=True, hazard_info="H225 H314"
        )
        db = _mock_db([[], [], [p]])
        warnings = check_inventory_safety(db)
        unrecognized = [
            w for w in warnings if w["warning_type"] == "unrecognized_hazard_codes"
        ]
        assert len(unrecognized) == 0


class TestCheckInventorySafetyAllGood:
    """No warnings when all products are properly configured."""

    def test_no_products(self):
        db = _mock_db([[], [], []])
        warnings = check_inventory_safety(db)
        assert warnings == []

    def test_non_hazardous_product_no_warnings(self):
        """Non-hazardous products should never generate warnings."""
        p = _make_product(
            id=10,
            name="SafeChem",
            is_hazardous=False,
            hazard_info=None,
            cas_number=None,
        )
        # All three queries filter on is_hazardous == True, so non-hazardous
        # products never appear in results.
        db = _mock_db([[], [], []])
        warnings = check_inventory_safety(db)
        assert warnings == []

    def test_fully_configured_product_no_warnings(self):
        """A hazardous product with full info and valid codes generates no warnings."""
        p = _make_product(
            id=11,
            name="FullChem",
            is_hazardous=True,
            hazard_info="H225 H314",
            cas_number="67-64-1",
        )
        db = _mock_db([[], [], [p]])
        warnings = check_inventory_safety(db)
        assert warnings == []


class TestCheckInventorySafetyCombined:
    """Multiple warning types in a single scan."""

    def test_mixed_warnings(self):
        p_no_info = _make_product(
            id=1, name="NoInfo", is_hazardous=True, hazard_info=None
        )
        p_no_cas = _make_product(
            id=2, name="NoCAS", is_hazardous=True, hazard_info="H225", cas_number=None
        )
        p_bad = _make_product(
            id=3, name="BadCodes", is_hazardous=True, hazard_info="dangerous stuff"
        )
        # Query 1: missing hazard_info -> [p_no_info]
        # Query 2: missing cas_number -> [p_no_cas]
        # Query 3: has hazard_info but bad codes -> [p_no_cas, p_bad]
        #   p_no_cas has valid H225 -> no unrecognized warning
        #   p_bad has no valid codes -> unrecognized warning
        db = _mock_db([[p_no_info], [p_no_cas], [p_no_cas, p_bad]])
        warnings = check_inventory_safety(db)
        types = {w["warning_type"] for w in warnings}
        assert "missing_hazard_info" in types
        assert "missing_cas_number" in types
        assert "unrecognized_hazard_codes" in types

    def test_warning_fields_structure(self):
        """Every warning has the required keys."""
        p = _make_product(id=1, name="X", is_hazardous=True, hazard_info=None)
        db = _mock_db([[p], [], []])
        warnings = check_inventory_safety(db)
        assert len(warnings) == 1
        w = warnings[0]
        for key in (
            "product_id",
            "product_name",
            "catalog_number",
            "warning_type",
            "severity",
            "message",
        ):
            assert key in w, f"Missing key: {key}"


# ===================================================================
# GHS_HAZARD_MAP data integrity
# ===================================================================


class TestGhsHazardMapIntegrity:
    """Verify the static data structure is well-formed."""

    def test_all_entries_have_required_keys(self):
        for code, entry in GHS_HAZARD_MAP.items():
            assert "category" in entry, f"{code} missing 'category'"
            assert "ppe" in entry, f"{code} missing 'ppe'"
            assert "disposal" in entry, f"{code} missing 'disposal'"

    def test_all_categories_are_strings(self):
        for code, entry in GHS_HAZARD_MAP.items():
            assert isinstance(entry["category"], str), f"{code} category not str"
            assert isinstance(entry["ppe"], str), f"{code} ppe not str"
            assert isinstance(entry["disposal"], str), f"{code} disposal not str"

    def test_map_has_euh_codes(self):
        assert "EUH071" in GHS_HAZARD_MAP

    def test_map_has_physical_hazards(self):
        for code in ("H200", "H225", "H240", "H250", "H260", "H270", "H280", "H290"):
            assert code in GHS_HAZARD_MAP, f"Missing physical hazard code {code}"

    def test_map_has_health_hazards(self):
        for code in ("H300", "H314", "H330", "H350", "H360", "H370"):
            assert code in GHS_HAZARD_MAP, f"Missing health hazard code {code}"

    def test_map_has_environmental_hazards(self):
        for code in ("H400", "H410", "H411", "H412", "H413"):
            assert code in GHS_HAZARD_MAP, f"Missing environmental hazard code {code}"
