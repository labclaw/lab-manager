"""Unit tests for vendor_normalize, vendor_urls, and serialization services."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from lab_manager.services.serialization import serialize_value
from lab_manager.services.vendor_normalize import (
    _normalize_key,
    normalize_vendor,
)
from lab_manager.services.vendor_urls import get_reorder_url


# ---------------------------------------------------------------------------
# _normalize_key
# ---------------------------------------------------------------------------


class TestNormalizeKey:
    """Tests for vendor_normalize._normalize_key."""

    def test_lowercase(self) -> None:
        assert _normalize_key("SIGMA-ALDRICH") == "sigma-aldrich"

    def test_strip_whitespace(self) -> None:
        assert _normalize_key("  Sigma-Aldrich  ") == "sigma-aldrich"

    def test_strip_tabs_and_newlines(self) -> None:
        assert _normalize_key("\tSigma-Aldrich\n") == "sigma-aldrich"

    def test_rstrip_trailing_dot(self) -> None:
        assert _normalize_key("Inc.") == "inc"

    def test_rstrip_multiple_trailing_dots(self) -> None:
        """rstrip('.') strips ALL trailing dots."""
        assert _normalize_key("Inc..") == "inc"

    def test_empty_string(self) -> None:
        assert _normalize_key("") == ""

    def test_only_whitespace(self) -> None:
        assert _normalize_key("   ") == ""

    def test_unicode_characters(self) -> None:
        assert _normalize_key("Invitrogen\u2122") == "invitrogen\u2122"

    def test_punctuation_preserved_except_trailing_dot(self) -> None:
        assert _normalize_key("Sigma-Aldrich, Inc.") == "sigma-aldrich, inc"

    def test_mixed_case_with_spaces(self) -> None:
        assert (
            _normalize_key("  Thermo Fisher Scientific  ") == "thermo fisher scientific"
        )

    def test_no_trailing_dot_unchanged(self) -> None:
        assert _normalize_key("Sigma-Aldrich") == "sigma-aldrich"

    def test_dot_in_middle_preserved(self) -> None:
        assert _normalize_key("Dr. Jones") == "dr. jones"


# ---------------------------------------------------------------------------
# normalize_vendor
# ---------------------------------------------------------------------------


class TestNormalizeVendor:
    """Tests for vendor_normalize.normalize_vendor."""

    # -- Null / empty inputs --

    def test_none_input(self) -> None:
        assert normalize_vendor(None) is None

    def test_empty_string(self) -> None:
        assert normalize_vendor("") == ""

    def test_whitespace_only(self) -> None:
        result = normalize_vendor("   ")
        assert result == "   "  # not in lookup, returned as-is

    # -- Sigma-Aldrich variations --

    def test_sigma_aldrich_exact(self) -> None:
        assert normalize_vendor("Sigma-Aldrich") == "Sigma-Aldrich"

    def test_sigma_aldrich_lowercase(self) -> None:
        assert normalize_vendor("sigma-aldrich") == "Sigma-Aldrich"

    def test_sigma_aldrich_uppercase(self) -> None:
        assert normalize_vendor("SIGMA-ALDRICH") == "Sigma-Aldrich"

    def test_sigma_aldrich_with_space(self) -> None:
        assert normalize_vendor("Sigma Aldrich") == "Sigma-Aldrich"

    def test_sigma_aldrich_inc_with_dot(self) -> None:
        assert normalize_vendor("Sigma-Aldrich, Inc.") == "Sigma-Aldrich"

    def test_sigma_aldrich_inc_without_dot(self) -> None:
        assert normalize_vendor("Sigma-Aldrich, Inc") == "Sigma-Aldrich"

    # -- MilliporeSigma / Merck --

    def test_milliporesigma(self) -> None:
        assert normalize_vendor("MilliporeSigma") == "MilliporeSigma"

    def test_milliporesigma_lowercase(self) -> None:
        assert normalize_vendor("milliporesigma") == "MilliporeSigma"

    def test_milliporesigma_corporation(self) -> None:
        assert normalize_vendor("MilliporeSigma Corporation") == "MilliporeSigma"

    def test_emd_millipore(self) -> None:
        assert normalize_vendor("EMD Millipore Corporation") == "MilliporeSigma"

    # -- Fisher Scientific --

    def test_fisher_scientific(self) -> None:
        assert normalize_vendor("Fisher Scientific") == "Fisher Scientific"

    def test_fisher_scientific_co(self) -> None:
        assert normalize_vendor("Fisher Scientific Co") == "Fisher Scientific"

    def test_fisher_scientific_co_dot(self) -> None:
        assert normalize_vendor("Fisher Scientific Co.") == "Fisher Scientific"

    def test_fisher_scientific_company(self) -> None:
        assert normalize_vendor("Fisher Scientific Company") == "Fisher Scientific"

    # -- Thermo Fisher --

    def test_thermofisher_scientific(self) -> None:
        assert normalize_vendor("ThermoFisher Scientific") == "Thermo Fisher Scientific"

    def test_thermo_fisher_full_name(self) -> None:
        assert (
            normalize_vendor("Thermo Fisher Scientific Chemicals Inc.")
            == "Thermo Fisher Scientific"
        )

    # -- Bio-Rad --

    def test_bio_rad(self) -> None:
        assert normalize_vendor("Bio-Rad") == "Bio-Rad Laboratories"

    def test_bio_rad_laboratories_inc(self) -> None:
        assert normalize_vendor("Bio-Rad Laboratories, Inc.") == "Bio-Rad Laboratories"

    # -- Invitrogen / Life Technologies --

    def test_invitrogen(self) -> None:
        assert normalize_vendor("Invitrogen") == "Invitrogen"

    def test_life_technologies(self) -> None:
        assert normalize_vendor("Life Technologies") == "Invitrogen"

    def test_invitrogen_by_life_tech(self) -> None:
        assert normalize_vendor("Invitrogen by Life Technologies") == "Invitrogen"

    def test_invitrogen_with_trademark(self) -> None:
        assert (
            normalize_vendor("Invitrogen\u2122 by Life Technologies\u2122")
            == "Invitrogen"
        )

    # -- McMaster-Carr --

    def test_mcmaster_carr(self) -> None:
        assert normalize_vendor("McMaster-Carr") == "McMaster-Carr"

    # -- Westnet --

    def test_westnet(self) -> None:
        assert normalize_vendor("Westnet") == "Westnet"

    def test_westnet_inc(self) -> None:
        assert normalize_vendor("Westnet Inc.") == "Westnet"

    def test_westnet_canton(self) -> None:
        assert normalize_vendor("Westnet - Canton") == "Westnet"

    # -- Genesee --

    def test_genesee_scientific(self) -> None:
        assert normalize_vendor("Genesee Scientific") == "Genesee Scientific"

    def test_genesee_scientific_llc(self) -> None:
        assert normalize_vendor("Genesee Scientific, LLC") == "Genesee Scientific"

    # -- MedChemExpress --

    def test_medchemexpress_llc(self) -> None:
        assert normalize_vendor("MedChemExpress LLC") == "MedChemExpress"

    def test_medchem_express_llc(self) -> None:
        assert normalize_vendor("MedChem Express LLC") == "MedChemExpress"

    # -- Patterson --

    def test_patterson_dental_supply(self) -> None:
        assert normalize_vendor("Patterson Dental Supply, Inc.") == "Patterson Dental"

    def test_patterson_logistics(self) -> None:
        assert (
            normalize_vendor("Patterson Logistics Services, Inc.") == "Patterson Dental"
        )

    # -- Medline --

    def test_medline(self) -> None:
        assert normalize_vendor("Medline") == "Medline Industries"

    def test_medline_industries_lp(self) -> None:
        assert normalize_vendor("Medline Industries LP") == "Medline Industries"

    # -- Grainger --

    def test_grainger(self) -> None:
        assert normalize_vendor("Grainger") == "Grainger"

    def test_ww_grainger(self) -> None:
        assert normalize_vendor("WW Grainger") == "Grainger"

    # -- CDW --

    def test_cdw_g(self) -> None:
        assert normalize_vendor("CDW-G") == "CDW"

    def test_cdw_logistics_llc(self) -> None:
        assert normalize_vendor("CDW Logistics LLC") == "CDW"

    # -- DigiKey --

    def test_digikey(self) -> None:
        assert normalize_vendor("DigiKey") == "DigiKey Electronics"

    def test_digikay_typo(self) -> None:
        assert normalize_vendor("Digikay") == "DigiKey Electronics"

    # -- PluriSelect --

    def test_pluriselect(self) -> None:
        assert normalize_vendor("PluriSelect USA, Inc.") == "PluriSelect"

    # -- Creative Biolabs --

    def test_creative_biolabs(self) -> None:
        assert normalize_vendor("Creative Biolabs") == "Creative Biolabs"

    def test_creative_biolabs_inc(self) -> None:
        assert normalize_vendor("Creative Biolabs Inc.") == "Creative Biolabs"

    # -- Nikon --

    def test_nikon(self) -> None:
        assert normalize_vendor("Nikon") == "Nikon Instruments"

    def test_nikon_instruments_consignment(self) -> None:
        assert normalize_vendor("Nikon Instruments Consignment") == "Nikon Instruments"

    # -- Unknown vendor passthrough --

    def test_unknown_vendor_returned_as_is(self) -> None:
        assert normalize_vendor("Unknown Vendor XYZ") == "Unknown Vendor XYZ"

    def test_case_preserved_for_unknown(self) -> None:
        assert normalize_vendor("Acme Corp") == "Acme Corp"

    def test_numeric_vendor_name(self) -> None:
        assert normalize_vendor("123 Vendor") == "123 Vendor"


# ---------------------------------------------------------------------------
# get_reorder_url
# ---------------------------------------------------------------------------


class TestGetReorderUrl:
    """Tests for vendor_urls.get_reorder_url."""

    # -- None / empty inputs --

    def test_none_vendor(self) -> None:
        assert get_reorder_url(None, "CAT123") is None  # type: ignore[arg-type]

    def test_none_catalog(self) -> None:
        assert get_reorder_url("Sigma-Aldrich", None) is None  # type: ignore[arg-type]

    def test_empty_vendor(self) -> None:
        assert get_reorder_url("", "CAT123") is None

    def test_empty_catalog(self) -> None:
        assert get_reorder_url("Sigma-Aldrich", "") is None

    def test_both_empty(self) -> None:
        assert get_reorder_url("", "") is None

    # -- Known vendor+catalog combos --

    def test_sigma_aldrich_url(self) -> None:
        url = get_reorder_url("Sigma-Aldrich", "SAB4500121")
        assert url == "https://www.sigmaaldrich.com/US/en/search/SAB4500121"

    def test_milliporesigma_url(self) -> None:
        url = get_reorder_url("MilliporeSigma", "HAWP29325")
        assert url == "https://www.sigmaaldrich.com/US/en/search/HAWP29325"

    def test_thermo_fisher_url(self) -> None:
        url = get_reorder_url("Thermo Fisher", "PI34567")
        assert url == "https://www.thermofisher.com/search/results?query=PI34567"

    def test_fisher_scientific_url(self) -> None:
        url = get_reorder_url("Fisher Scientific", "S25849")
        assert url == "https://www.fishersci.com/us/en/search/S25849"

    def test_bio_rad_url(self) -> None:
        url = get_reorder_url("Bio-Rad", "5000205")
        assert url == "https://www.bio-rad.com/en-us/search?query=5000205"

    def test_addgene_url(self) -> None:
        url = get_reorder_url("Addgene", "12345")
        assert url == "https://www.addgene.org/search/all/?q=12345"

    def test_mcmaster_carr_url(self) -> None:
        url = get_reorder_url("McMaster-Carr", "92196A052")
        assert url == "https://www.mcmaster.com/92196A052"

    def test_invitrogen_url(self) -> None:
        url = get_reorder_url("Invitrogen", "RPMI1640")
        assert url == "https://www.thermofisher.com/search/results?query=RPMI1640"

    # -- Fuzzy matching (vendor_key in key or key in vendor_key) --

    def test_vendor_key_contained_in_input(self) -> None:
        """Input 'Bio-Rad Laboratories' contains 'bio-rad'."""
        url = get_reorder_url("Bio-Rad Laboratories", "5000205")
        assert url is not None
        assert "bio-rad.com" in url

    def test_input_contained_in_vendor_key(self) -> None:
        """Input 'vwr' is contained in vendor key 'vwr'."""
        url = get_reorder_url("VWR", "12345")
        assert url is not None
        assert "vwr.com" in url

    def test_case_insensitive_vendor_match(self) -> None:
        url = get_reorder_url("SIGMA-ALDRICH", "SAB123")
        assert url is not None
        assert "sigmaaldrich.com" in url

    def test_case_insensitive_thermo(self) -> None:
        url = get_reorder_url("THERMO FISHER", "ABC123")
        assert url is not None
        assert "thermofisher.com" in url

    # -- Unknown vendor falls back to Google --

    def test_unknown_vendor_google_fallback(self) -> None:
        url = get_reorder_url("Acme Biotech", "XYZ999")
        assert url is not None
        assert "google.com" in url
        assert "Acme Biotech" in url
        assert "XYZ999" in url

    def test_unknown_vendor_google_search_format(self) -> None:
        url = get_reorder_url("Mystery Corp", "CAT001")
        assert url == "https://www.google.com/search?q=Mystery Corp+CAT001+order"

    # -- Special characters in catalog number --

    def test_catalog_with_slash(self) -> None:
        url = get_reorder_url("Sigma-Aldrich", "SAB/4500121")
        assert url is not None
        assert "SAB/4500121" in url

    def test_catalog_with_hash(self) -> None:
        url = get_reorder_url("ATCC", "CRL#1658")
        assert url is not None
        assert "CRL#1658" in url

    def test_catalog_with_space(self) -> None:
        url = get_reorder_url("Fisher Scientific", "CAT 12345")
        assert url is not None
        assert "CAT 12345" in url

    def test_catalog_with_special_chars(self) -> None:
        url = get_reorder_url("Bio-Rad", "500-0205&x=1")
        assert url is not None
        assert "500-0205&x=1" in url

    # -- Vendor with whitespace around name --

    def test_vendor_with_leading_trailing_spaces(self) -> None:
        url = get_reorder_url("  Sigma-Aldrich  ", "SAB123")
        assert url is not None
        assert "sigmaaldrich.com" in url


# ---------------------------------------------------------------------------
# serialize_value
# ---------------------------------------------------------------------------


class TestSerializeValue:
    """Tests for serialization.serialize_value."""

    # -- None --

    def test_none(self) -> None:
        assert serialize_value(None) is None

    # -- bool (must check before int since bool is subclass of int) --

    def test_bool_true(self) -> None:
        assert serialize_value(True) is True

    def test_bool_false(self) -> None:
        assert serialize_value(False) is False

    # -- int --

    def test_int(self) -> None:
        assert serialize_value(42) == 42
        assert isinstance(serialize_value(42), int)

    def test_int_zero(self) -> None:
        assert serialize_value(0) == 0

    def test_int_negative(self) -> None:
        assert serialize_value(-100) == -100

    # -- float --

    def test_float(self) -> None:
        result = serialize_value(3.14)
        assert result == pytest.approx(3.14)

    def test_float_zero(self) -> None:
        assert serialize_value(0.0) == 0.0

    def test_float_negative(self) -> None:
        result = serialize_value(-2.718)
        assert result == pytest.approx(-2.718)

    # -- str --

    def test_str(self) -> None:
        assert serialize_value("hello") == "hello"

    def test_str_empty(self) -> None:
        assert serialize_value("") == ""

    def test_str_unicode(self) -> None:
        assert serialize_value("invitrogen\u2122") == "invitrogen\u2122"

    # -- Decimal --

    def test_decimal(self) -> None:
        assert serialize_value(Decimal("19.99")) == "19.99"

    def test_decimal_zero(self) -> None:
        assert serialize_value(Decimal("0")) == "0"

    def test_decimal_large_precision(self) -> None:
        val = Decimal("123456789.123456789")
        assert serialize_value(val) == "123456789.123456789"

    def test_decimal_negative(self) -> None:
        assert serialize_value(Decimal("-50.5")) == "-50.5"

    # -- datetime --

    def test_datetime(self) -> None:
        dt = datetime(2024, 6, 15, 10, 30, 45)
        assert serialize_value(dt) == "2024-06-15T10:30:45"

    def test_datetime_with_microseconds(self) -> None:
        dt = datetime(2024, 1, 1, 0, 0, 0, 123456)
        assert serialize_value(dt) == "2024-01-01T00:00:00.123456"

    def test_datetime_utc(self) -> None:
        from datetime import timezone

        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert serialize_value(dt) == "2024-06-15T12:00:00+00:00"

    # -- date --

    def test_date(self) -> None:
        d = date(2024, 6, 15)
        assert serialize_value(d) == "2024-06-15"

    def test_date_epoch(self) -> None:
        d = date(1970, 1, 1)
        assert serialize_value(d) == "1970-01-01"

    # -- list --

    def test_list(self) -> None:
        assert serialize_value([1, 2, 3]) == [1, 2, 3]

    def test_empty_list(self) -> None:
        assert serialize_value([]) == []

    def test_nested_list(self) -> None:
        assert serialize_value([1, [2, 3]]) == [1, [2, 3]]

    # -- dict --

    def test_dict(self) -> None:
        assert serialize_value({"key": "value"}) == {"key": "value"}

    def test_empty_dict(self) -> None:
        assert serialize_value({}) == {}

    def test_nested_dict(self) -> None:
        assert serialize_value({"a": {"b": 1}}) == {"a": {"b": 1}}

    # -- bytes (fallback to str) --

    def test_bytes_fallback_to_str(self) -> None:
        result = serialize_value(b"hello")
        assert result == "b'hello'"

    # -- UUID (fallback to str) --

    def test_uuid_fallback_to_str(self) -> None:
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = serialize_value(u)
        assert result == "12345678-1234-5678-1234-567812345678"

    # -- numpy-like int64/float64 (duck-typed via type name) --

    def test_numpy_int64_like(self) -> None:
        class FakeInt64:
            def __int__(self) -> int:
                return 42

            def __repr__(self) -> str:
                return "FakeInt64(42)"

        fake = FakeInt64()
        assert type(fake).__name__ == "FakeInt64"
        # Won't match int64/int32 — falls to str fallback
        assert serialize_value(fake) == "FakeInt64(42)"

    def test_numpy_int32_like(self) -> None:
        """Create an object with __name__ spoofed to 'int32'."""

        class int32:  # noqa: N801 — intentionally named to match type check
            def __int__(self) -> int:
                return 7

        val = int32()
        assert serialize_value(val) == 7

    def test_numpy_float64_like(self) -> None:
        class float64:  # noqa: N801
            def __float__(self) -> float:
                return 3.14

        val = float64()
        result = serialize_value(val)
        assert result == pytest.approx(3.14)

    def test_numpy_float32_like(self) -> None:
        class float32:  # noqa: N801
            def __float__(self) -> float:
                return 2.5

        val = float32()
        result = serialize_value(val)
        assert result == pytest.approx(2.5)

    # -- Arbitrary object fallback --

    def test_arbitrary_object_fallback_to_str(self) -> None:
        class CustomObj:
            def __str__(self) -> str:
                return "custom_object"

        assert serialize_value(CustomObj()) == "custom_object"

    def test_set_fallback_to_str(self) -> None:
        result = serialize_value({1, 2, 3})
        assert isinstance(result, str)

    def test_tuple_fallback_to_str(self) -> None:
        result = serialize_value((1, 2, 3))
        assert isinstance(result, str)

    # -- datetime checked before date (important: datetime is subclass of date) --

    def test_datetime_not_treated_as_date(self) -> None:
        """datetime is a subclass of date; ensure isoformat includes time."""
        dt = datetime(2024, 3, 15, 8, 30, 0)
        result = serialize_value(dt)
        assert "T" in result
        assert result == "2024-03-15T08:30:00"
