"""Tests for vendor name normalization."""

import pytest

from lab_manager.services.vendor_normalize import VENDOR_ALIASES, normalize_vendor


class TestNormalizeVendor:
    """Unit tests for normalize_vendor()."""

    def test_none_returns_none(self):
        assert normalize_vendor(None) is None

    def test_empty_string_returns_empty(self):
        assert normalize_vendor("") == ""

    def test_exact_match_lowercase(self):
        assert normalize_vendor("sigma-aldrich") == "Sigma-Aldrich"

    def test_case_insensitive(self):
        assert normalize_vendor("SIGMA-ALDRICH") == "Sigma-Aldrich"
        assert normalize_vendor("Sigma-Aldrich") == "Sigma-Aldrich"
        assert normalize_vendor("sigma-ALDRICH") == "Sigma-Aldrich"

    def test_trailing_dot_stripped(self):
        assert normalize_vendor("Fisher Scientific Co.") == "Fisher Scientific"

    def test_whitespace_stripped(self):
        assert normalize_vendor("  sigma-aldrich  ") == "Sigma-Aldrich"

    def test_milliporesigma_variants(self):
        assert normalize_vendor("MilliporeSigma") == "MilliporeSigma"
        assert normalize_vendor("MilliporeSigma Corporation") == "MilliporeSigma"
        assert normalize_vendor("EMD Millipore Corporation") == "MilliporeSigma"

    def test_fisher_scientific_variants(self):
        assert normalize_vendor("FISHER SCIENTIFIC CO") == "Fisher Scientific"
        assert normalize_vendor("FISHER SCIENTIFIC") == "Fisher Scientific"
        assert normalize_vendor("Fisher Scientific Company") == "Fisher Scientific"

    def test_thermo_fisher(self):
        assert (
            normalize_vendor("THERMO FISHER SCIENTIFIC CHEMICALS INC.")
            == "Thermo Fisher Scientific"
        )
        assert normalize_vendor("ThermoFisher SCIENTIFIC") == "Thermo Fisher Scientific"

    def test_invitrogen_life_technologies(self):
        assert normalize_vendor("invitrogen") == "Invitrogen"
        assert normalize_vendor("Life Technologies") == "Invitrogen"
        assert normalize_vendor("invitrogen by life technologies") == "Invitrogen"

    def test_bio_rad(self):
        assert normalize_vendor("Bio-Rad") == "Bio-Rad Laboratories"
        assert normalize_vendor("Bio-Rad Laboratories, Inc.") == "Bio-Rad Laboratories"

    def test_digikey_typo(self):
        assert normalize_vendor("Digikay") == "DigiKey Electronics"
        assert normalize_vendor("DigiKey") == "DigiKey Electronics"

    def test_unknown_vendor_passthrough(self):
        assert normalize_vendor("Acme Labs") == "Acme Labs"
        assert normalize_vendor("Some New Vendor") == "Some New Vendor"

    def test_westnet_variants(self):
        assert normalize_vendor("Westnet") == "Westnet"
        assert normalize_vendor("Westnet - Canton") == "Westnet"
        assert normalize_vendor("Westnet Inc.") == "Westnet"

    def test_medchemexpress_variants(self):
        assert normalize_vendor("MedChemExpress LLC") == "MedChemExpress"
        assert normalize_vendor("MedChem Express LLC") == "MedChemExpress"

    def test_pluriselect_variants(self):
        assert normalize_vendor("PluriSelect usa, Inc.") == "PluriSelect"
        assert normalize_vendor("Pluriselect usa, Inc") == "PluriSelect"

    def test_creative_biolabs(self):
        assert normalize_vendor("Creative Biolabs") == "Creative Biolabs"
        assert normalize_vendor("Creative Biolabs Inc.") == "Creative Biolabs"

    def test_nikon_variants(self):
        assert normalize_vendor("Nikon") == "Nikon Instruments"
        assert normalize_vendor("Nikon Instruments Consignment") == "Nikon Instruments"

    def test_grainger_variants(self):
        assert normalize_vendor("Grainger") == "Grainger"
        assert normalize_vendor("WW Grainger") == "Grainger"

    def test_cdw_variants(self):
        assert normalize_vendor("CDW-G") == "CDW"
        assert normalize_vendor("CDW Logistics LLC") == "CDW"

    def test_every_alias_has_canonical_value(self):
        """Every alias key must map to a non-empty canonical name."""
        for alias_key, canonical in VENDOR_ALIASES.items():
            assert canonical, f"Alias '{alias_key}' maps to empty canonical name"
            assert canonical.strip() == canonical, (
                f"Canonical '{canonical}' has whitespace"
            )

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("sigma-aldrich, inc.", "Sigma-Aldrich"),
            ("Sigma Aldrich, Inc.", "Sigma-Aldrich"),
            ("FISHER SCIENTIFIC CO.", "Fisher Scientific"),
            ("Patterson Dental Supply, Inc.", "Patterson Dental"),
            ("Patterson Logistics Services, Inc.", "Patterson Dental"),
            ("Medline Industries LP", "Medline Industries"),
            ("Genesee Scientific, LLC", "Genesee Scientific"),
        ],
    )
    def test_parametrized_aliases(self, raw, expected):
        assert normalize_vendor(raw) == expected
