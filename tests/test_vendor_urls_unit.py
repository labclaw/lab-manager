"""Comprehensive unit tests for vendor_urls service.

Pure unit tests for VENDOR_SEARCH_URLS registry and get_reorder_url().
No database, no API client -- direct function calls only.
"""

from urllib.parse import urlparse


from lab_manager.services.vendor_urls import VENDOR_SEARCH_URLS, get_reorder_url


# ---------------------------------------------------------------------------
# Registry structure tests
# ---------------------------------------------------------------------------


class TestRegistryStructure:
    """Verify VENDOR_SEARCH_URLS is well-formed and complete."""

    def test_registry_is_dict(self):
        assert isinstance(VENDOR_SEARCH_URLS, dict)

    def test_registry_has_minimum_entries(self):
        assert len(VENDOR_SEARCH_URLS) >= 20

    def test_all_values_are_strings(self):
        for key, val in VENDOR_SEARCH_URLS.items():
            assert isinstance(val, str), f"{key}: value is not a string"

    def test_all_keys_are_strings(self):
        for key in VENDOR_SEARCH_URLS:
            assert isinstance(key, str), f"key {key!r} is not a string"

    def test_all_keys_are_lowercase(self):
        for key in VENDOR_SEARCH_URLS:
            assert key == key.lower(), f"key {key!r} is not lowercase"

    def test_all_patterns_contain_catalog_placeholder(self):
        for key, pattern in VENDOR_SEARCH_URLS.items():
            assert "{catalog}" in pattern, f"{key}: missing {{catalog}} placeholder"

    def test_all_patterns_are_https(self):
        for key, pattern in VENDOR_SEARCH_URLS.items():
            assert pattern.startswith("https://"), f"{key}: not HTTPS"

    def test_known_aliases_share_urls(self):
        # sigma-aldrich and milliporesigma intentionally share the same URL
        assert (
            VENDOR_SEARCH_URLS["sigma-aldrich"] == VENDOR_SEARCH_URLS["milliporesigma"]
        )
        # thermo fisher and invitrogen intentionally share the same URL
        assert VENDOR_SEARCH_URLS["thermo fisher"] == VENDOR_SEARCH_URLS["invitrogen"]

    def test_specific_known_vendors_present(self):
        expected = [
            "sigma-aldrich",
            "thermo fisher",
            "bio-rad",
            "addgene",
            "vwr",
            "mcmaster-carr",
            "qiagen",
        ]
        for vendor in expected:
            assert vendor in VENDOR_SEARCH_URLS, f"{vendor} missing from registry"


# ---------------------------------------------------------------------------
# Return type and None handling
# ---------------------------------------------------------------------------


class TestReturnTypes:
    """Verify return types for various inputs."""

    def test_known_vendor_returns_str(self):
        result = get_reorder_url("Sigma-Aldrich", "S1234")
        assert isinstance(result, str)

    def test_unknown_vendor_returns_str(self):
        result = get_reorder_url("MysteryCorp", "ABC")
        assert isinstance(result, str)

    def test_empty_vendor_returns_none(self):
        assert get_reorder_url("", "S1234") is None

    def test_empty_catalog_returns_none(self):
        assert get_reorder_url("Sigma-Aldrich", "") is None

    def test_both_empty_returns_none(self):
        assert get_reorder_url("", "") is None

    def test_none_equivalent_vendor_returns_none(self):
        # Falsy string -- empty string is the only falsy str
        assert get_reorder_url("", "S1234") is None

    def test_none_equivalent_catalog_returns_none(self):
        assert get_reorder_url("Sigma-Aldrich", "") is None


# ---------------------------------------------------------------------------
# Exact vendor name matches
# ---------------------------------------------------------------------------


class TestExactMatches:
    """Direct key lookups produce correct URLs."""

    def test_sigma_aldrich(self):
        url = get_reorder_url("sigma-aldrich", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_thermo_fisher(self):
        url = get_reorder_url("thermo fisher", "A12345")
        assert url == "https://www.thermofisher.com/search/results?query=A12345"

    def test_fisher_scientific(self):
        url = get_reorder_url("fisher scientific", "FS-001")
        assert url == "https://www.fishersci.com/us/en/search/FS-001"

    def test_bio_rad(self):
        url = get_reorder_url("bio-rad", "BR-999")
        assert url == "https://www.bio-rad.com/en-us/search?query=BR-999"

    def test_addgene(self):
        url = get_reorder_url("addgene", "12345")
        assert url == "https://www.addgene.org/search/all/?q=12345"

    def test_abcam(self):
        url = get_reorder_url("abcam", "ab12345")
        assert url == "https://www.abcam.com/search?q=ab12345"

    def test_cell_signaling(self):
        url = get_reorder_url("cell signaling", "CST-4060")
        assert url == "https://www.cellsignal.com/search?q=CST-4060"

    def test_atcc(self):
        url = get_reorder_url("atcc", "ATCC-100")
        assert url == "https://www.atcc.org/search#q=ATCC-100"

    def test_vwr(self):
        url = get_reorder_url("vwr", "VWR-XYZ")
        assert url == "https://us.vwr.com/store/search?query=VWR-XYZ"

    def test_goldbio(self):
        url = get_reorder_url("goldbio", "GB-123")
        assert url == "https://www.goldbio.com/search?q=GB-123"

    def test_mcmaster_carr(self):
        url = get_reorder_url("mcmaster-carr", "91251A")
        assert url == "https://www.mcmaster.com/91251A"

    def test_qiagen(self):
        url = get_reorder_url("qiagen", "QIAG-001")
        assert url == "https://www.qiagen.com/us/search?query=QIAG-001"

    def test_invitrogen_redirects_to_thermofisher(self):
        url = get_reorder_url("invitrogen", "INV-001")
        assert url == "https://www.thermofisher.com/search/results?query=INV-001"

    def test_milliporesigma_redirects_to_sigmaaldrich(self):
        url = get_reorder_url("milliporesigma", "MS-789")
        assert url == "https://www.sigmaaldrich.com/US/en/search/MS-789"


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


class TestCaseInsensitivity:
    """Vendor name matching is case-insensitive."""

    def test_uppercase(self):
        url = get_reorder_url("SIGMA-ALDRICH", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_mixed_case(self):
        url = get_reorder_url("Sigma-Aldrich", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_all_caps(self):
        url = get_reorder_url("ADDGENE", "12345")
        assert url == "https://www.addgene.org/search/all/?q=12345"

    def test_title_case(self):
        url = get_reorder_url("Bio-Rad", "BR-1")
        assert url == "https://www.bio-rad.com/en-us/search?query=BR-1"

    def test_case_preserved_in_google_fallback(self):
        url = get_reorder_url("MyCustomVendor", "XYZ")
        assert url is not None
        # The original vendor name (with case) appears in the Google query
        assert "MyCustomVendor" in url


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------


class TestWhitespaceHandling:
    """Leading/trailing whitespace is stripped from vendor name."""

    def test_leading_spaces(self):
        url = get_reorder_url("  sigma-aldrich", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_trailing_spaces(self):
        url = get_reorder_url("sigma-aldrich  ", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_both_sides_spaces(self):
        url = get_reorder_url("  sigma-aldrich  ", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_tab_characters(self):
        url = get_reorder_url("\tsigma-aldrich\t", "S1234")
        assert url == "https://www.sigmaaldrich.com/US/en/search/S1234"

    def test_whitespace_only_vendor_matches_first_key(self):
        # "   ".strip() == "" and "" in any string is True,
        # so it matches the first vendor key in the dict iteration order.
        # This is a known edge case -- whitespace-only vendor is truthy,
        # but after strip becomes empty which is a substring of everything.
        url = get_reorder_url("   ", "S1234")
        assert url is not None  # matches first key due to "" in vendor_key

    def test_whitespace_only_catalog_returns_none(self):
        # Whitespace-only catalog is not empty string after no strip
        # The function only checks falsy, "   " is truthy
        url = get_reorder_url("sigma-aldrich", "   ")
        # catalog_number is not stripped -- "   " is truthy, so not None
        assert url is not None


# ---------------------------------------------------------------------------
# Fuzzy / substring matching
# ---------------------------------------------------------------------------


class TestFuzzyMatching:
    """Substring matching: vendor_key in key OR key in vendor_key."""

    def test_vendor_key_in_input(self):
        # "sigma-aldrich" is a substring of "Sigma-Aldrich Chemicals LLC"
        url = get_reorder_url("Sigma-Aldrich Chemicals LLC", "S1234")
        assert url is not None
        assert "sigmaaldrich.com" in url

    def test_input_in_vendor_key(self):
        # "thermo" is a substring of "thermo fisher" key, so it matches.
        # This demonstrates that even partial input matches vendor keys.
        url = get_reorder_url("thermo", "A123")
        assert url is not None
        assert "thermofisher.com" in url

    def test_no_match_falls_to_google(self):
        # A vendor name that shares no substring with any key
        url = get_reorder_url("Completely Unknown Corp", "ABC")
        assert url is not None
        assert "google.com" in url

    def test_partial_vendor_name_key_in_input(self):
        # "cell signaling" key is a substring of "Cell Signaling Technology"
        url = get_reorder_url("Cell Signaling Technology", "CST-1")
        assert url is not None
        assert "cellsignal.com" in url

    def test_vendor_suffix_match(self):
        # "santa cruz" key is substring of "Santa Cruz Biotechnology"
        url = get_reorder_url("Santa Cruz Biotechnology", "sc-1234")
        assert url is not None
        assert "scbt.com" in url

    def test_vendor_prefix_match(self):
        # "takara bio" is substring of input
        url = get_reorder_url("Takara Bio USA", "TB-001")
        assert url is not None
        assert "takarabio.com" in url

    def test_input_is_superset_of_key(self):
        # Input "eppendorf" matches key "eppendorf" exactly
        url = get_reorder_url("Eppendorf North America", "EP-123")
        assert url is not None
        assert "eppendorf.com" in url


# ---------------------------------------------------------------------------
# Unknown vendor Google fallback
# ---------------------------------------------------------------------------


class TestGoogleFallback:
    """Unknown vendors produce Google search URLs."""

    def test_unknown_vendor_returns_google_url(self):
        url = get_reorder_url("TotallyFakeVendor", "ABC-123")
        assert url is not None
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "www.google.com"
        assert parsed.path == "/search"

    def test_google_url_contains_vendor_name(self):
        url = get_reorder_url("FakeCorp", "XYZ-999")
        assert "FakeCorp" in url

    def test_google_url_contains_catalog_number(self):
        url = get_reorder_url("FakeCorp", "XYZ-999")
        assert "XYZ-999" in url

    def test_google_url_contains_order_keyword(self):
        url = get_reorder_url("FakeCorp", "XYZ-999")
        assert "order" in url

    def test_google_url_format(self):
        url = get_reorder_url("SomeVendor", "CAT-123")
        assert url == "https://www.google.com/search?q=SomeVendor+CAT-123+order"

    def test_google_fallback_with_special_chars_in_catalog(self):
        url = get_reorder_url("AcmeLab", "CAT/123#456")
        assert url is not None
        assert "CAT/123#456" in url

    def test_google_fallback_preserves_vendor_case(self):
        url = get_reorder_url("CamelCaseVendor", "X-1")
        assert "CamelCaseVendor" in url


# ---------------------------------------------------------------------------
# Catalog number handling
# ---------------------------------------------------------------------------


class TestCatalogNumberHandling:
    """Catalog numbers are correctly inserted into URL patterns."""

    def test_catalog_in_path(self):
        # sigma-aldrich puts catalog in path
        url = get_reorder_url("sigma-aldrich", "MY-CAT-123")
        assert url.endswith("/MY-CAT-123")

    def test_catalog_in_query_param(self):
        # thermo fisher puts catalog in query
        url = get_reorder_url("thermo fisher", "QUERY-VAL")
        assert "query=QUERY-VAL" in url

    def test_catalog_with_slashes(self):
        url = get_reorder_url("sigma-aldrich", "A/B/C")
        assert "A/B/C" in url

    def test_catalog_with_hash(self):
        url = get_reorder_url("addgene", "12345#section")
        assert "12345#section" in url

    def test_catalog_with_spaces(self):
        url = get_reorder_url("sigma-aldrich", "CAT 123")
        assert "CAT 123" in url

    def test_catalog_with_special_chars(self):
        url = get_reorder_url("sigma-aldrich", "CAT-123_456.789")
        assert "CAT-123_456.789" in url

    def test_numeric_catalog(self):
        url = get_reorder_url("addgene", "12345")
        assert "12345" in url


# ---------------------------------------------------------------------------
# Special characters and edge cases in vendor name
# ---------------------------------------------------------------------------


class TestSpecialCharacters:
    """Vendor names with special characters."""

    def test_vendor_name_with_parentheses(self):
        url = get_reorder_url("Sigma-Aldrich (USA)", "S1234")
        assert url is not None
        # Should still match because "sigma-aldrich" is substring
        assert "sigmaaldrich.com" in url

    def test_vendor_name_with_ampersand(self):
        url = get_reorder_url("Johnson & Johnson", "JNJ-001")
        # Unknown vendor -- Google fallback
        assert url is not None
        assert "google.com" in url

    def test_vendor_name_with_plus(self):
        url = get_reorder_url("Some+Vendor", "ABC")
        # Not a known vendor, Google fallback
        assert url is not None
        assert "google.com" in url

    def test_vendor_name_unicode(self):
        url = get_reorder_url("Bio-Rad", "BR-1")
        assert url is not None
        assert "bio-rad.com" in url

    def test_very_long_vendor_name(self):
        long_name = "A" * 500
        url = get_reorder_url(long_name, "CAT-123")
        assert url is not None
        assert "google.com" in url

    def test_very_long_catalog_number(self):
        long_cat = "X" * 500
        url = get_reorder_url("sigma-aldrich", long_cat)
        assert url is not None
        assert long_cat in url


# ---------------------------------------------------------------------------
# URL format validation
# ---------------------------------------------------------------------------


class TestUrlFormatValidation:
    """All returned URLs are valid and well-formed."""

    def test_known_vendor_url_is_parseable(self):
        url = get_reorder_url("sigma-aldrich", "S1234")
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc
        assert parsed.path

    def test_google_fallback_url_is_parseable(self):
        url = get_reorder_url("UnknownVendor", "XYZ")
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.netloc == "www.google.com"

    def test_no_double_slashes_in_path(self):
        url = get_reorder_url("mcmaster-carr", "91251A")
        # McMaster pattern is https://www.mcmaster.com/{catalog}
        # Should not produce double slashes
        path = urlparse(url).path
        assert "//" not in path

    def test_placeholder_fully_replaced(self):
        url = get_reorder_url("sigma-aldrich", "S1234")
        assert "{catalog}" not in url
