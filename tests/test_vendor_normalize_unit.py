"""Comprehensive unit tests for vendor_normalize module.

Covers _normalize_key, normalize_vendor, VENDOR_ALIASES structure,
edge cases (None, empty, unicode, whitespace, special chars),
and every alias entry in the lookup table.
"""

import pytest

from lab_manager.services.vendor_normalize import (
    VENDOR_ALIASES,
    _LOOKUP,
    _normalize_key,
    normalize_vendor,
)


# ---------------------------------------------------------------------------
# _normalize_key unit tests
# ---------------------------------------------------------------------------


class TestNormalizeKey:
    """Tests for the internal _normalize_key helper."""

    def test_lowercase_conversion(self):
        assert _normalize_key("SIGMA-ALDRICH") == "sigma-aldrich"

    def test_strip_leading_whitespace(self):
        assert _normalize_key("  fisher scientific") == "fisher scientific"

    def test_strip_trailing_whitespace(self):
        assert _normalize_key("fisher scientific  ") == "fisher scientific"

    def test_strip_both_whitespace(self):
        assert _normalize_key("  bio-rad  ") == "bio-rad"

    def test_rstrip_trailing_dots(self):
        assert _normalize_key("inc.") == "inc"

    def test_rstrip_trailing_multiple_dots(self):
        assert _normalize_key("inc...") == "inc"

    def test_no_rstrip_leading_dots(self):
        assert _normalize_key(".inc") == ".inc"

    def test_empty_string_stays_empty(self):
        assert _normalize_key("") == ""

    def test_only_whitespace_becomes_empty(self):
        assert _normalize_key("   ") == ""

    def test_only_dots_after_strip(self):
        assert _normalize_key("...") == ""

    def test_whitespace_then_dots(self):
        assert _normalize_key("  inc.  ") == "inc"

    def test_already_normalized(self):
        assert _normalize_key("sigma-aldrich") == "sigma-aldrich"

    def test_mixed_case(self):
        assert _normalize_key("ThErMoFiShEr") == "thermofisher"

    def test_unicode_preserved(self):
        """Unicode chars like trademark symbol should pass through lowercase."""
        assert _normalize_key("\u2122") == "\u2122"


# ---------------------------------------------------------------------------
# normalize_vendor — null/empty/falsy inputs
# ---------------------------------------------------------------------------


class TestNormalizeVendorFalsyInputs:
    """Tests for falsy input handling."""

    def test_none_returns_none(self):
        assert normalize_vendor(None) is None

    def test_empty_string_returns_empty(self):
        assert normalize_vendor("") == ""

    def test_only_whitespace_returns_whitespace(self):
        """Whitespace-only string is falsy via 'not name', returns itself."""
        assert normalize_vendor("   ") == "   "

    def test_zero_not_string(self):
        """Integer 0 is falsy, returned as-is (not a string but function allows it)."""
        result = normalize_vendor(0)
        assert result == 0


# ---------------------------------------------------------------------------
# normalize_vendor — case insensitivity
# ---------------------------------------------------------------------------


class TestNormalizeVendorCaseInsensitivity:
    """Verify case-insensitive lookup for representative aliases."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("SIGMA-ALDRICH", "Sigma-Aldrich"),
            ("Sigma-Aldrich", "Sigma-Aldrich"),
            ("sIgMa-AlDrIcH", "Sigma-Aldrich"),
            ("FISHER SCIENTIFIC", "Fisher Scientific"),
            ("fisher SCIENTIFIC", "Fisher Scientific"),
            ("MILLIPORESIGMA", "MilliporeSigma"),
            ("bio-rad", "Bio-Rad Laboratories"),
            ("BIO-RAD", "Bio-Rad Laboratories"),
            ("INVITROGEN", "Invitrogen"),
            ("THERMOFISHER SCIENTIFIC", "Thermo Fisher Scientific"),
            ("MCMASTER-CARR", "McMaster-Carr"),
            ("GRAINGER", "Grainger"),
            ("DIGIKEY", "DigiKey Electronics"),
            ("NIKON", "Nikon Instruments"),
        ],
    )
    def test_case_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


# ---------------------------------------------------------------------------
# normalize_vendor — whitespace handling
# ---------------------------------------------------------------------------


class TestNormalizeVendorWhitespace:
    """Verify leading/trailing whitespace is stripped before lookup."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("  sigma-aldrich", "Sigma-Aldrich"),
            ("sigma-aldrich  ", "Sigma-Aldrich"),
            ("\tsigma-aldrich\t", "Sigma-Aldrich"),
            ("\n sigma-aldrich \n", "Sigma-Aldrich"),
            ("  fisher scientific co  ", "Fisher Scientific"),
            ("  milliporesigma  ", "MilliporeSigma"),
        ],
    )
    def test_whitespace_stripped(self, raw, expected):
        assert normalize_vendor(raw) == expected


# ---------------------------------------------------------------------------
# normalize_vendor — trailing dot stripping
# ---------------------------------------------------------------------------


class TestNormalizeVendorTrailingDot:
    """Verify trailing dots are stripped during key normalization."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Sigma-Aldrich, Inc.", "Sigma-Aldrich"),
            ("Fisher Scientific Co.", "Fisher Scientific"),
            ("Bio-Rad Laboratories, Inc.", "Bio-Rad Laboratories"),
            ("Genesee Scientific, LLC.", "Genesee Scientific"),
            ("sigma-aldrich.", "Sigma-Aldrich"),
        ],
    )
    def test_trailing_dot_stripped(self, raw, expected):
        assert normalize_vendor(raw) == expected


# ---------------------------------------------------------------------------
# normalize_vendor — specific vendor groups
# ---------------------------------------------------------------------------


class TestSigmaAldrichGroup:
    """Sigma-Aldrich / MilliporeSigma / Merck variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("sigma-aldrich", "Sigma-Aldrich"),
            ("sigma-aldrich, inc.", "Sigma-Aldrich"),
            ("sigma-aldrich, inc", "Sigma-Aldrich"),
            ("sigma aldrich", "Sigma-Aldrich"),
            ("sigma aldrich, inc.", "Sigma-Aldrich"),
            ("milliporesigma", "MilliporeSigma"),
            ("milliporesigma corporation", "MilliporeSigma"),
            ("emd millipore corporation", "MilliporeSigma"),
        ],
    )
    def test_sigma_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestThermoFisherGroup:
    """Thermo Fisher / Fisher Scientific variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("fisher scientific", "Fisher Scientific"),
            ("fisher scientific co", "Fisher Scientific"),
            ("fisher scientific co.", "Fisher Scientific"),
            ("fisher scientific company", "Fisher Scientific"),
            ("fisher scientific technology inc.", "Fisher Scientific"),
            ("thermo fisher scientific chemicals inc.", "Thermo Fisher Scientific"),
            ("thermofisher scientific", "Thermo Fisher Scientific"),
        ],
    )
    def test_fisher_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestBioRadGroup:
    """Bio-Rad variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("bio-rad", "Bio-Rad Laboratories"),
            ("bio-rad laboratories, inc.", "Bio-Rad Laboratories"),
        ],
    )
    def test_biorad_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestInvitrogenGroup:
    """Invitrogen / Life Technologies variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("invitrogen", "Invitrogen"),
            ("invitrogen by life technologies", "Invitrogen"),
            ("life technologies", "Invitrogen"),
            ("life technologies corpora", "Invitrogen"),
        ],
    )
    def test_invitrogen_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected

    def test_invitrogen_trademark_unicode(self):
        """The trademark unicode variant in VENDOR_ALIASES must resolve."""
        assert (
            normalize_vendor("invitrogen\u2122 by life technologies\u2122")
            == "Invitrogen"
        )


class TestWestnetGroup:
    """Westnet variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("westnet", "Westnet"),
            ("westnet - canton", "Westnet"),
            ("westnet inc.", "Westnet"),
        ],
    )
    def test_westnet_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestMedChemExpressGroup:
    """MedChemExpress variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("medchemexpress llc", "MedChemExpress"),
            ("medchem express llc", "MedChemExpress"),
        ],
    )
    def test_medchemexpress_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestPattersonGroup:
    """Patterson variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("patterson dental supply, inc.", "Patterson Dental"),
            ("patterson logistics services, inc.", "Patterson Dental"),
        ],
    )
    def test_patterson_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestMedlineGroup:
    """Medline variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("medline", "Medline Industries"),
            ("medline industries lp", "Medline Industries"),
        ],
    )
    def test_medline_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestGraingerGroup:
    """Grainger variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("grainger", "Grainger"),
            ("ww grainger", "Grainger"),
        ],
    )
    def test_grainger_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestCDWGroup:
    """CDW variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("cdw-g", "CDW"),
            ("cdw logistics llc", "CDW"),
        ],
    )
    def test_cdw_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestDigiKeyGroup:
    """DigiKey variants including typo."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("digikey", "DigiKey Electronics"),
            ("digikey electronics", "DigiKey Electronics"),
            ("digikay", "DigiKey Electronics"),
        ],
    )
    def test_digikey_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestPluriSelectGroup:
    """PluriSelect variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("pluriselect usa, inc.", "PluriSelect"),
            ("pluriselect usa, inc", "PluriSelect"),
        ],
    )
    def test_pluriselect_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestCreativeBiolabsGroup:
    """Creative Biolabs variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("creative biolabs", "Creative Biolabs"),
            ("creative biolabs inc.", "Creative Biolabs"),
        ],
    )
    def test_creative_biolabs_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestNikonGroup:
    """Nikon variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("nikon", "Nikon Instruments"),
            ("nikon instruments consignment", "Nikon Instruments"),
        ],
    )
    def test_nikon_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestGeneseeGroup:
    """Genesee Scientific variants."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("genesee scientific", "Genesee Scientific"),
            ("genesee scientific, llc", "Genesee Scientific"),
        ],
    )
    def test_genesee_variants(self, raw, expected):
        assert normalize_vendor(raw) == expected


class TestMcMasterCarr:
    """McMaster-Carr."""

    def test_mcmaster_carr(self):
        assert normalize_vendor("mcmaster-carr") == "McMaster-Carr"


# ---------------------------------------------------------------------------
# normalize_vendor — passthrough for unknown vendors
# ---------------------------------------------------------------------------


class TestNormalizeVendorPassthrough:
    """Unknown vendor names must be returned unchanged."""

    @pytest.mark.parametrize(
        "name",
        [
            "Acme Labs",
            "Unknown Vendor Corp",
            "Some New Vendor",
            "Totally Made Up Company Inc.",
            "Not A Real Vendor",
        ],
    )
    def test_unknown_vendor_returned_as_is(self, name):
        assert normalize_vendor(name) == name

    def test_unknown_with_special_characters(self):
        assert normalize_vendor("Vendor @ 2024 #1") == "Vendor @ 2024 #1"

    def test_unknown_with_unicode(self):
        assert normalize_vendor("Vendor\u2122") == "Vendor\u2122"

    def test_single_character(self):
        assert normalize_vendor("A") == "A"

    def test_very_long_name(self):
        long_name = "A" * 500
        assert normalize_vendor(long_name) == long_name

    def test_name_with_newlines(self):
        assert normalize_vendor("Vendor\nName") == "Vendor\nName"

    def test_numeric_string(self):
        assert normalize_vendor("12345") == "12345"


# ---------------------------------------------------------------------------
# VENDOR_ALIASES structural integrity
# ---------------------------------------------------------------------------


class TestVendorAliasesStructure:
    """Validate VENDOR_ALIASES dictionary structure and invariants."""

    def test_aliases_is_dict(self):
        assert isinstance(VENDOR_ALIASES, dict)

    def test_aliases_not_empty(self):
        assert len(VENDOR_ALIASES) > 0

    def test_all_keys_are_strings(self):
        for key in VENDOR_ALIASES:
            assert isinstance(key, str), f"Key {key!r} is not a string"

    def test_all_values_are_strings(self):
        for key, val in VENDOR_ALIASES.items():
            assert isinstance(val, str), f"Value for key {key!r} is not a string"

    def test_no_empty_keys(self):
        for key in VENDOR_ALIASES:
            assert key, "Empty key found in VENDOR_ALIASES"

    def test_no_empty_values(self):
        for key, val in VENDOR_ALIASES.items():
            assert val, f"Key {key!r} maps to empty value"

    def test_no_whitespace_only_keys(self):
        for key in VENDOR_ALIASES:
            assert key.strip(), f"Whitespace-only key found: {key!r}"

    def test_no_whitespace_only_values(self):
        for key, val in VENDOR_ALIASES.items():
            assert val.strip(), f"Whitespace-only value for key {key!r}"

    def test_canonical_names_have_no_leading_trailing_whitespace(self):
        for key, val in VENDOR_ALIASES.items():
            assert val == val.strip(), (
                f"Canonical value {val!r} for key {key!r} has leading/trailing whitespace"
            )

    def test_keys_are_lowercase(self):
        """All raw alias keys should be lowercase for readability."""
        for key in VENDOR_ALIASES:
            assert key == key.lower(), f"Key {key!r} is not lowercase"


# ---------------------------------------------------------------------------
# _LOOKUP table integrity
# ---------------------------------------------------------------------------


class TestLookupTable:
    """Validate the pre-built _LOOKUP table."""

    def test_lookup_is_dict(self):
        assert isinstance(_LOOKUP, dict)

    def test_lookup_has_fewer_or_equal_entries(self):
        """_LOOKUP may have fewer entries than VENDOR_ALIASES due to key normalization dedup."""
        assert len(_LOOKUP) <= len(VENDOR_ALIASES)
        assert len(_LOOKUP) > 0

    def test_lookup_keys_are_normalized(self):
        """Every _LOOKUP key should be lowercase, stripped, no trailing dots."""
        for key in _LOOKUP:
            assert key == key.lower(), f"_LOOKUP key {key!r} is not lowercase"
            assert key == key.strip(), f"_LOOKUP key {key!r} is not stripped"
            assert not key.endswith("."), f"_LOOKUP key {key!r} has trailing dot"

    def test_lookup_contains_all_alias_keys_normalized(self):
        """Every VENDOR_ALIASES key (normalized) should be in _LOOKUP."""
        for alias_key in VENDOR_ALIASES:
            normalized = _normalize_key(alias_key)
            assert normalized in _LOOKUP, (
                f"Normalized key {normalized!r} from alias {alias_key!r} not in _LOOKUP"
            )

    def test_lookup_values_match_aliases(self):
        """_LOOKUP values should match VENDOR_ALIASES values."""
        for alias_key, canonical in VENDOR_ALIASES.items():
            normalized = _normalize_key(alias_key)
            assert _LOOKUP[normalized] == canonical, (
                f"_LOOKUP[{normalized!r}] = {_LOOKUP[normalized]!r}, "
                f"expected {canonical!r}"
            )


# ---------------------------------------------------------------------------
# Exhaustive: every alias maps correctly via normalize_vendor
# ---------------------------------------------------------------------------


class TestAllAliasesExhaustive:
    """Every alias in VENDOR_ALIASES must resolve correctly through normalize_vendor."""

    @pytest.mark.parametrize(
        "alias_key,expected",
        list(VENDOR_ALIASES.items()),
        ids=[f"alias-{i}" for i in range(len(VENDOR_ALIASES))],
    )
    def test_alias_resolves(self, alias_key, expected):
        assert normalize_vendor(alias_key) == expected


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """normalize_vendor(normalize_vendor(x)) == normalize_vendor(x)."""

    @pytest.mark.parametrize(
        "name",
        [
            "sigma-aldrich",
            "Sigma-Aldrich, Inc.",
            "Fisher Scientific Co.",
            "Unknown Vendor",
            "bio-rad",
            "",
        ],
    )
    def test_idempotent(self, name):
        first = normalize_vendor(name)
        second = normalize_vendor(first)
        assert second == first


# ---------------------------------------------------------------------------
# Canonical names that also exist as alias keys
# ---------------------------------------------------------------------------


class TestCanonicalNamePassthrough:
    """Canonical names themselves should pass through unchanged."""

    @pytest.mark.parametrize(
        "canonical",
        [
            "Sigma-Aldrich",
            "MilliporeSigma",
            "Fisher Scientific",
            "Thermo Fisher Scientific",
            "Bio-Rad Laboratories",
            "Invitrogen",
            "McMaster-Carr",
            "Westnet",
            "Genesee Scientific",
            "MedChemExpress",
            "Patterson Dental",
            "Medline Industries",
            "Grainger",
            "CDW",
            "DigiKey Electronics",
            "PluriSelect",
            "Creative Biolabs",
            "Nikon Instruments",
        ],
    )
    def test_canonical_name_unchanged(self, canonical):
        """Canonical names that are NOT alias keys pass through as-is."""
        result = normalize_vendor(canonical)
        # If the canonical form happens to be an alias key, it maps to itself
        # Otherwise it passes through unchanged
        normalized_key = _normalize_key(canonical)
        if normalized_key in _LOOKUP:
            assert result == _LOOKUP[normalized_key]
        else:
            assert result == canonical
