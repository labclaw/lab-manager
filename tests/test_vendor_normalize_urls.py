"""Tests for vendor name normalization and URL generation."""

from lab_manager.services.vendor_normalize import (
    normalize_vendor,
    VENDOR_ALIASES,
    _normalize_key,
)
from lab_manager.services.vendor_urls import get_reorder_url, VENDOR_SEARCH_URLS


class TestVendorNormalize:
    """Tests for vendor_normalize.py"""

    def test_exact_match(self):
        assert normalize_vendor("Sigma-Aldrich") == "Sigma-Aldrich"

    def test_case_insensitive(self):
        assert normalize_vendor("sigma-aldrich") == "Sigma-Aldrich"
        assert normalize_vendor("SIGMA-ALDRICH") == "Sigma-Aldrich"
        assert normalize_vendor("Sigma-Aldrich") == "Sigma-Aldrich"

    def test_alias_with_suffix(self):
        assert normalize_vendor("sigma-aldrich, inc.") == "Sigma-Aldrich"
        assert normalize_vendor("sigma-aldrich, inc") == "Sigma-Aldrich"

    def test_spaces_vs_hyphens(self):
        assert normalize_vendor("sigma aldrich") == "Sigma-Aldrich"

    def test_fisher_scientific_aliases(self):
        assert normalize_vendor("fisher scientific") == "Fisher Scientific"
        assert normalize_vendor("fisher scientific co") == "Fisher Scientific"
        assert normalize_vendor("fisher scientific co.") == "Fisher Scientific"
        assert normalize_vendor("fisher scientific company") == "Fisher Scientific"

    def test_thermo_fisher(self):
        assert normalize_vendor("thermofisher scientific") == "Thermo Fisher Scientific"
        assert (
            normalize_vendor("thermo fisher scientific chemicals inc.")
            == "Thermo Fisher Scientific"
        )

    def test_bio_rad(self):
        assert normalize_vendor("bio-rad") == "Bio-Rad Laboratories"
        assert normalize_vendor("bio-rad laboratories, inc.") == "Bio-Rad Laboratories"

    def test_invitrogen(self):
        assert normalize_vendor("invitrogen") == "Invitrogen"
        assert normalize_vendor("life technologies") == "Invitrogen"

    def test_unknown_vendor_unchanged(self):
        assert normalize_vendor("Acme Corp") == "Acme Corp"

    def test_none_returns_none(self):
        assert normalize_vendor(None) is None

    def test_empty_string_returns_empty(self):
        assert normalize_vendor("") == ""

    def test_whitespace_only(self):
        assert normalize_vendor("   ") == "   "

    def test_trailing_dot_stripped(self):
        # "sigma-aldrich." should match "sigma-aldrich" after stripping
        result = normalize_vendor("sigma-aldrich.")
        assert result == "Sigma-Aldrich"

    def test_all_aliases_resolve(self):
        """Every alias value should be a known canonical form."""
        canonical = set(VENDOR_ALIASES.values())
        for key, value in VENDOR_ALIASES.items():
            assert value in canonical, f"Alias {key!r} maps to unknown {value!r}"

    def test_normalize_key_idempotent(self):
        assert _normalize_key("  Fisher Scientific Co.  ") == "fisher scientific co"


class TestVendorUrls:
    """Tests for vendor_urls.py"""

    def test_sigma_aldrich_url(self):
        url = get_reorder_url("Sigma-Aldrich", "SRE0001")
        assert url is not None
        assert "sigmaaldrich.com" in url
        assert "SRE0001" in url

    def test_fisher_scientific_url(self):
        url = get_reorder_url("Fisher Scientific", "Cat123")
        assert url is not None
        assert "fishersci.com" in url
        assert "Cat123" in url

    def test_bio_rad_url(self):
        url = get_reorder_url("Bio-Rad", "456-7890")
        assert url is not None
        assert "bio-rad.com" in url

    def test_case_insensitive_match(self):
        url1 = get_reorder_url("Sigma-Aldrich", "A123")
        url2 = get_reorder_url("sigma-aldrich", "A123")
        assert url1 == url2

    def test_unknown_vendor_google_fallback(self):
        url = get_reorder_url("Unknown Vendor", "CAT-999")
        assert url is not None
        assert "google.com" in url
        assert "Unknown Vendor" in url
        assert "CAT-999" in url

    def test_empty_vendor_returns_none(self):
        assert get_reorder_url("", "CAT-001") is None

    def test_none_vendor_returns_none(self):
        assert get_reorder_url(None, "CAT-001") is None

    def test_empty_catalog_returns_none(self):
        assert get_reorder_url("Sigma-Aldrich", "") is None

    def test_none_catalog_returns_none(self):
        assert get_reorder_url("Sigma-Aldrich", None) is None

    def test_substring_match(self):
        """Vendor URL lookup uses fuzzy substring matching."""
        url = get_reorder_url("cell signaling technology", "1234")
        assert url is not None
        assert "cellsignal.com" in url

    def test_all_patterns_have_placeholder(self):
        """Every URL pattern should contain {catalog}."""
        for vendor, pattern in VENDOR_SEARCH_URLS.items():
            assert "{catalog}" in pattern, (
                f"{vendor} URL missing {{catalog}} placeholder"
            )

    def test_url_contains_catalog_number(self):
        url = get_reorder_url("addgene", "12345")
        assert url is not None
        assert "12345" in url
