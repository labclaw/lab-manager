"""Unit tests for lab_manager.services.pubchem — fully mocked HTTP calls."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from lab_manager.services.pubchem import (
    _CACHE,
    _CACHE_MAX,
    _MIN_INTERVAL,
    _PROPERTIES,
    _fetch_cas,
    _fetch_properties,
    _props_to_result,
    _cache_put,
    clear_cache,
    enrich_product,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cache():
    """Clear the module-level cache before and after every test."""
    clear_cache()
    yield
    clear_cache()


def _make_props_response(
    cid: int = 2244,
    molecular_weight: str = "180.16",
    molecular_formula: str = "C6H12O6",
    smiles: str = "C(C1C(C(C(C(O1)O)O)O)O)O",
    iupac_name: str = "(3R,4S,5S,6R)-6-(hydroxymethyl)oxane-2,3,4,5-tetrol",
) -> dict[str, Any]:
    """Build a PubChem PropertyTable response."""
    return {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": cid,
                    "MolecularWeight": molecular_weight,
                    "MolecularFormula": molecular_formula,
                    "CanonicalSMILES": smiles,
                    "IUPACName": iupac_name,
                }
            ]
        }
    }


def _make_synonyms_response(
    cid: int = 2244, synonyms: list[str] | None = None
) -> dict[str, Any]:
    """Build a PubChem synonyms response."""
    if synonyms is None:
        synonyms = ["glucose", "50-99-7", "D-glucopyranose", "D-Glucose"]
    return {"InformationList": {"Information": [{"CID": cid, "Synonym": synonyms}]}}


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    raise_on_status: bool = False,
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    if raise_on_status and status_code >= 400:
        exc = httpx.HTTPStatusError(
            message=f"{status_code} Error",
            request=MagicMock(),
            response=resp,
        )
        resp.raise_for_status.side_effect = exc
    return resp


# ===========================================================================
# _rate_limit
# ===========================================================================


class TestRateLimit:
    """Tests for the _rate_limit enforcement function."""

    @patch("lab_manager.services.pubchem.time")
    def test_no_sleep_when_interval_exceeded(self, mock_time):
        """Should NOT sleep if enough time has passed since last request."""
        import lab_manager.services.pubchem as mod

        mod._last_request_time = 0.0
        mock_time.monotonic.side_effect = [10.0, 10.001]
        mock_time.sleep = MagicMock()

        mod._rate_limit()

        mock_time.sleep.assert_not_called()

    @patch("lab_manager.services.pubchem.time")
    def test_sleeps_when_interval_not_met(self, mock_time):
        """Should sleep for the remaining interval duration."""
        import lab_manager.services.pubchem as mod

        mod._last_request_time = 0.0
        mock_time.monotonic.side_effect = [0.05, 0.25]
        mock_time.sleep = MagicMock()

        mod._rate_limit()

        mock_time.sleep.assert_called_once()
        sleep_arg = mock_time.sleep.call_args[0][0]
        assert sleep_arg > 0
        assert sleep_arg <= _MIN_INTERVAL

    @patch("lab_manager.services.pubchem.time")
    def test_updates_last_request_time(self, mock_time):
        """Should set _last_request_time after sleeping."""
        import lab_manager.services.pubchem as mod

        mod._last_request_time = 0.0
        mock_time.monotonic.side_effect = [0.05, 0.30]
        mock_time.sleep = MagicMock()

        mod._rate_limit()

        assert mod._last_request_time == 0.30

    @patch("lab_manager.services.pubchem.time")
    def test_exact_interval_no_sleep(self, mock_time):
        """At exactly _MIN_INTERVAL elapsed, no sleep needed."""
        import lab_manager.services.pubchem as mod

        mod._last_request_time = 0.0
        mock_time.monotonic.side_effect = [_MIN_INTERVAL, _MIN_INTERVAL + 0.001]
        mock_time.sleep = MagicMock()

        mod._rate_limit()

        mock_time.sleep.assert_not_called()


# ===========================================================================
# _fetch_properties
# ===========================================================================


class TestFetchProperties:
    """Tests for _fetch_properties internal function."""

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_successful_fetch(self, mock_rl, mock_get):
        """Returns first property dict on 200 response."""
        data = _make_props_response()
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_properties("aspirin")

        assert result is not None
        assert result["CID"] == 2244
        assert result["MolecularWeight"] == "180.16"
        assert result["MolecularFormula"] == "C6H12O6"

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_404(self, mock_rl, mock_get):
        """Returns None when compound not found (404)."""
        mock_get.return_value = _mock_response(status_code=404)

        result = _fetch_properties("nonexistent_compound_xyz")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_429_rate_limit(self, mock_rl, mock_get):
        """Returns None when PubChem rate limits (429)."""
        mock_get.return_value = _mock_response(status_code=429)

        result = _fetch_properties("ethanol")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_timeout(self, mock_rl, mock_get):
        """Returns None on httpx.TimeoutException."""
        mock_get.side_effect = httpx.TimeoutException("timeout")

        result = _fetch_properties("acetone")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_http_status_error(self, mock_rl, mock_get):
        """Returns None on httpx.HTTPStatusError (e.g. 500)."""
        mock_get.return_value = _mock_response(status_code=500, raise_on_status=True)

        result = _fetch_properties("methanol")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_unexpected_exception(self, mock_rl, mock_get):
        """Returns None on unexpected exceptions (e.g. ConnectionError)."""
        mock_get.side_effect = httpx.ConnectError("connection refused")

        result = _fetch_properties("water")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_when_empty_properties_list(self, mock_rl, mock_get):
        """Returns None when PropertyTable.Properties is empty."""
        mock_get.return_value = _mock_response(
            json_data={"PropertyTable": {"Properties": []}}
        )

        result = _fetch_properties("blank")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_when_missing_property_table(self, mock_rl, mock_get):
        """Returns None when response has no PropertyTable key."""
        mock_get.return_value = _mock_response(json_data={"SomeOtherKey": "value"})

        result = _fetch_properties("missing_table")

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_first_result_when_multiple(self, mock_rl, mock_get):
        """Returns only the first item when multiple properties are returned."""
        data = {
            "PropertyTable": {
                "Properties": [
                    {"CID": 100, "MolecularWeight": "50.0"},
                    {"CID": 200, "MolecularWeight": "100.0"},
                ]
            }
        }
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_properties("multi")

        assert result["CID"] == 100

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_url_construction_with_namespace(self, mock_rl, mock_get):
        """Constructs correct URL with the given namespace."""
        data = _make_props_response()
        mock_get.return_value = _mock_response(json_data=data)

        _fetch_properties("2244", namespace="cid")

        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "/compound/cid/2244/property/" in url

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_default_namespace_is_name(self, mock_rl, mock_get):
        """Default namespace is 'name'."""
        data = _make_props_response()
        mock_get.return_value = _mock_response(json_data=data)

        _fetch_properties("aspirin")

        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "/compound/name/aspirin/property/" in url

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_url_contains_all_property_fields(self, mock_rl, mock_get):
        """URL requests all expected property fields."""
        data = _make_props_response()
        mock_get.return_value = _mock_response(json_data=data)

        _fetch_properties("test")

        url = mock_get.call_args[0][0]
        for prop in _PROPERTIES.split(","):
            assert prop in url

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_uses_correct_timeout_and_follow_redirects(self, mock_rl, mock_get):
        """Passes timeout and follow_redirects to httpx.get."""
        data = _make_props_response()
        mock_get.return_value = _mock_response(json_data=data)

        _fetch_properties("aspirin")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 3.0
        assert call_kwargs["follow_redirects"] is True

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_calls_rate_limit(self, mock_rl, mock_get):
        """Calls _rate_limit before making the request."""
        mock_get.return_value = _mock_response(json_data=_make_props_response())

        _fetch_properties("aspirin")

        mock_rl.assert_called_once()


# ===========================================================================
# _fetch_cas
# ===========================================================================


class TestFetchCas:
    """Tests for _fetch_cas internal function."""

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_finds_cas_number(self, mock_rl, mock_get):
        """Extracts CAS number from synonyms list."""
        data = _make_synonyms_response(
            synonyms=["glucose", "50-99-7", "D-glucose", "some-other-synonym"]
        )
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_cas(2244)

        assert result == "50-99-7"

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_when_no_cas_in_synonyms(self, mock_rl, mock_get):
        """Returns None when no synonym matches CAS pattern."""
        data = _make_synonyms_response(synonyms=["glucose", "D-glucose", "no-cas-here"])
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_cas(2244)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_non_200(self, mock_rl, mock_get):
        """Returns None when API returns non-200 status."""
        mock_get.return_value = _mock_response(status_code=404)

        result = _fetch_cas(99999999)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_on_exception(self, mock_rl, mock_get):
        """Returns None on any exception."""
        mock_get.side_effect = httpx.TimeoutException("timeout")

        result = _fetch_cas(2244)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_when_empty_synonyms(self, mock_rl, mock_get):
        """Returns None when synonyms list is empty."""
        data = _make_synonyms_response(synonyms=[])
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_cas(2244)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_when_empty_information_list(self, mock_rl, mock_get):
        """Returns None when InformationList.Information is empty."""
        mock_get.return_value = _mock_response(
            json_data={"InformationList": {"Information": []}}
        )

        result = _fetch_cas(2244)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_none_when_missing_information_list(self, mock_rl, mock_get):
        """Returns None when response lacks InformationList."""
        mock_get.return_value = _mock_response(json_data={"OtherKey": "value"})

        result = _fetch_cas(2244)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_matches_various_cas_formats(self, mock_rl, mock_get):
        """Matches CAS numbers with varying digit counts."""
        # 7-digit prefix: 1234567-89-0
        data = _make_synonyms_response(synonyms=["1234567-89-0"])
        mock_get.return_value = _mock_response(json_data=data)
        assert _fetch_cas(1) == "1234567-89-0"

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_matches_two_digit_prefix_cas(self, mock_rl, mock_get):
        """Matches shortest valid CAS (2-digit prefix)."""
        data = _make_synonyms_response(synonyms=["50-00-0"])
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_cas(1)

        assert result == "50-00-0"

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_rejects_invalid_cas_format_single_digit_prefix(self, mock_rl, mock_get):
        """Rejects CAS-like strings with only 1 digit before first hyphen."""
        data = _make_synonyms_response(synonyms=["5-00-0"])
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_cas(1)

        assert result is None

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_returns_first_cas_when_multiple(self, mock_rl, mock_get):
        """Returns the first CAS match when multiple CAS numbers exist."""
        data = _make_synonyms_response(
            synonyms=["first-cas-12-3", "50-99-7", "7732-18-5"]
        )
        mock_get.return_value = _mock_response(json_data=data)

        result = _fetch_cas(1)

        assert result == "50-99-7"

    @patch("lab_manager.services.pubchem.httpx.get")
    @patch("lab_manager.services.pubchem._rate_limit")
    def test_url_contains_cid(self, mock_rl, mock_get):
        """Constructs correct URL with the given CID."""
        data = _make_synonyms_response()
        mock_get.return_value = _mock_response(json_data=data)

        _fetch_cas(12345)

        url = mock_get.call_args[0][0]
        assert "/compound/cid/12345/synonyms/JSON" in url


# ===========================================================================
# _props_to_result
# ===========================================================================


class TestPropsToResult:
    """Tests for _props_to_result conversion function."""

    def test_full_properties(self):
        """Converts all fields when present."""
        props = {
            "CID": 2244,
            "MolecularWeight": "180.16",
            "MolecularFormula": "C6H12O6",
            "CanonicalSMILES": "CC(=O)Oc1ccccc1C(=O)O",
            "IUPACName": "2-acetyloxybenzoic acid",
        }

        result = _props_to_result(props, cas="50-99-7")

        assert result["pubchem_cid"] == 2244
        assert result["molecular_weight"] == 180.16
        assert result["molecular_formula"] == "C6H12O6"
        assert result["smiles"] == "CC(=O)Oc1ccccc1C(=O)O"
        assert result["iupac_name"] == "2-acetyloxybenzoic acid"
        assert result["cas_number"] == "50-99-7"

    def test_minimal_properties(self):
        """Handles minimal properties with only CID."""
        props = {"CID": 123}

        result = _props_to_result(props)

        assert result["pubchem_cid"] == 123
        assert "molecular_weight" not in result
        assert "molecular_formula" not in result
        assert "smiles" not in result
        assert "iupac_name" not in result
        assert "cas_number" not in result

    def test_empty_props(self):
        """Returns empty dict when no fields are present."""
        result = _props_to_result({})

        assert result == {}

    def test_none_cid_excluded(self):
        """Excludes pubchem_cid when CID is None."""
        props = {"CID": None, "MolecularWeight": "100.0"}

        result = _props_to_result(props)

        assert "pubchem_cid" not in result
        assert result["molecular_weight"] == 100.0

    def test_none_molecular_weight_excluded(self):
        """Excludes molecular_weight when MolecularWeight is None."""
        props = {"CID": 1, "MolecularWeight": None}

        result = _props_to_result(props)

        assert result["pubchem_cid"] == 1
        assert "molecular_weight" not in result

    def test_empty_string_formula_excluded(self):
        """Excludes molecular_formula when MolecularFormula is empty string."""
        props = {"MolecularFormula": ""}

        result = _props_to_result(props)

        assert "molecular_formula" not in result

    def test_empty_string_smiles_excluded(self):
        """Excludes smiles when CanonicalSMILES is empty string."""
        props = {"CanonicalSMILES": ""}

        result = _props_to_result(props)

        assert "smiles" not in result

    def test_empty_string_iupac_excluded(self):
        """Excludes iupac_name when IUPACName is empty string."""
        props = {"IUPACName": ""}

        result = _props_to_result(props)

        assert "iupac_name" not in result

    def test_cas_number_included_when_provided(self):
        """Includes cas_number when CAS string is provided."""
        result = _props_to_result({}, cas="50-99-7")

        assert result["cas_number"] == "50-99-7"

    def test_cas_number_excluded_when_none(self):
        """Excludes cas_number when CAS is None."""
        result = _props_to_result({}, cas=None)

        assert "cas_number" not in result

    def test_cas_number_excluded_when_not_passed(self):
        """Excludes cas_number when CAS argument is not provided."""
        result = _props_to_result({})

        assert "cas_number" not in result

    def test_molecular_weight_converted_to_float(self):
        """Converts MolecularWeight string to float."""
        props = {"MolecularWeight": "180.16"}

        result = _props_to_result(props)

        assert isinstance(result["molecular_weight"], float)
        assert result["molecular_weight"] == 180.16

    def test_cid_converted_to_int(self):
        """Converts CID to int even if it arrives as string."""
        props = {"CID": "2244"}

        result = _props_to_result(props)

        assert isinstance(result["pubchem_cid"], int)
        assert result["pubchem_cid"] == 2244

    def test_partial_properties(self):
        """Handles partial properties with only some fields."""
        props = {
            "CID": 2244,
            "MolecularFormula": "C6H12O6",
        }

        result = _props_to_result(props)

        assert result["pubchem_cid"] == 2244
        assert result["molecular_formula"] == "C6H12O6"
        assert "molecular_weight" not in result
        assert "smiles" not in result
        assert "iupac_name" not in result


# ===========================================================================
# _cache_put
# ===========================================================================


class TestCachePut:
    """Tests for _cache_put internal function."""

    def test_stores_value_in_cache(self):
        """Stores a key-value pair in the cache."""
        _cache_put("test_key", {"pubchem_cid": 1})

        assert "test_key" in _CACHE
        assert _CACHE["test_key"]["pubchem_cid"] == 1

    def test_overwrites_existing_key(self):
        """Overwrites value for an existing key."""
        _cache_put("key1", {"pubchem_cid": 1})
        _cache_put("key1", {"pubchem_cid": 2})

        assert _CACHE["key1"]["pubchem_cid"] == 2

    def test_evicts_oldest_when_full(self):
        """Evicts the first (oldest) entry when cache reaches max size."""
        # Fill cache to max
        for i in range(_CACHE_MAX):
            _cache_put(f"key_{i}", {"cid": i})

        assert len(_CACHE) == _CACHE_MAX

        # Add one more — should evict oldest
        _cache_put("new_key", {"cid": 999})

        assert len(_CACHE) == _CACHE_MAX
        assert "key_0" not in _CACHE
        assert "new_key" in _CACHE

    def test_evicts_correct_oldest_entry(self):
        """Verifies eviction removes the first inserted key, not any other."""
        _cache_put("oldest", {"cid": 1})
        _cache_put("middle", {"cid": 2})
        _cache_put("newest", {"cid": 3})

        # Force eviction by filling to max
        for i in range(_CACHE_MAX - 3):
            _cache_put(f"fill_{i}", {"cid": i})

        assert len(_CACHE) == _CACHE_MAX

        _cache_put("extra", {"cid": 999})
        assert "oldest" not in _CACHE
        assert "middle" in _CACHE


# ===========================================================================
# clear_cache
# ===========================================================================


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clears_all_entries(self):
        """Removes all entries from the cache."""
        _cache_put("a", {"cid": 1})
        _cache_put("b", {"cid": 2})

        assert len(_CACHE) == 2

        clear_cache()

        assert len(_CACHE) == 0

    def test_clear_on_empty_cache_is_safe(self):
        """Calling clear_cache on an already-empty cache is a no-op."""
        clear_cache()
        clear_cache()

        assert len(_CACHE) == 0


# ===========================================================================
# enrich_product
# ===========================================================================


class TestEnrichProduct:
    """Tests for the public enrich_product function."""

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_enrich_by_name_success(self, mock_fetch, mock_cas):
        """Returns enriched dict when compound found by name."""
        mock_fetch.return_value = {
            "CID": 2244,
            "MolecularWeight": "180.16",
            "MolecularFormula": "C6H12O6",
            "CanonicalSMILES": "glucose_smiles",
            "IUPACName": "glucose_iupac",
        }
        mock_cas.return_value = "50-99-7"

        result = enrich_product("aspirin")

        assert result["pubchem_cid"] == 2244
        assert result["cas_number"] == "50-99-7"
        assert result["molecular_weight"] == 180.16

    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_returns_empty_dict_when_not_found(self, mock_fetch):
        """Returns empty dict when compound not found."""
        mock_fetch.return_value = None

        result = enrich_product("totally_fake_compound")

        assert result == {}

    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_fallback_to_catalog_number(self, mock_fetch):
        """Tries catalog_number when name lookup fails."""
        call_count = 0

        def side_effect(identifier, namespace="name"):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # name lookup fails
            return {
                "CID": 100,
                "MolecularWeight": "50.0",
            }  # catalog number succeeds

        mock_fetch.side_effect = side_effect

        result = enrich_product("unknown_name", catalog_number="CAT-123")

        assert call_count == 2
        assert result["pubchem_cid"] == 100

    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_no_fallback_when_no_catalog_number(self, mock_fetch):
        """Does not try fallback when catalog_number is None."""
        mock_fetch.return_value = None

        enrich_product("unknown")

        assert mock_fetch.call_count == 1

    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_no_fallback_when_name_succeeds(self, mock_fetch):
        """Does not try catalog_number when name lookup succeeds."""
        mock_fetch.return_value = {"CID": 1, "MolecularWeight": "10.0"}

        enrich_product("aspirin", catalog_number="CAT-123")

        assert mock_fetch.call_count == 1

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_caches_result(self, mock_fetch, mock_cas):
        """Subsequent calls with same args return cached result."""
        mock_fetch.return_value = {"CID": 1, "MolecularWeight": "10.0"}
        mock_cas.return_value = "50-00-0"

        result1 = enrich_product("water")
        result2 = enrich_product("water")

        assert result1 is result2
        # Only called once — second call used cache
        assert mock_fetch.call_count == 1

    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_caches_empty_result(self, mock_fetch):
        """Caches empty results too, preventing repeated lookups."""
        mock_fetch.return_value = None

        result1 = enrich_product("nonexistent")
        result2 = enrich_product("nonexistent")

        assert result1 == {}
        assert result2 == {}
        assert mock_fetch.call_count == 1

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_different_args_not_shared_cache(self, mock_fetch, mock_cas):
        """Different name/catalog combos use different cache keys."""
        mock_fetch.return_value = {"CID": 1, "MolecularWeight": "10.0"}
        mock_cas.return_value = None

        enrich_product("water")
        enrich_product("ethanol")

        assert mock_fetch.call_count == 2

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_skips_cas_fetch_when_no_cid(self, mock_fetch, mock_cas):
        """Does not call _fetch_cas when props lack CID."""
        mock_fetch.return_value = {"MolecularWeight": "10.0"}

        enrich_product("no_cid_compound")

        mock_cas.assert_not_called()

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_fetches_cas_when_cid_present(self, mock_fetch, mock_cas):
        """Calls _fetch_cas when CID is present in properties."""
        mock_fetch.return_value = {"CID": 2244, "MolecularWeight": "180.16"}
        mock_cas.return_value = "50-99-7"

        enrich_product("glucose")

        mock_cas.assert_called_once_with(2244)

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_cache_key_includes_name_and_catalog(self, mock_fetch, mock_cas):
        """Cache key is constructed from name + catalog_number."""
        mock_fetch.return_value = {"CID": 1}
        mock_cas.return_value = None

        enrich_product("test", catalog_number="CAT1")
        enrich_product("test", catalog_number="CAT2")

        assert mock_fetch.call_count == 2

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_cache_key_same_with_same_args(self, mock_fetch, mock_cas):
        """Same name + same catalog_number hits cache."""
        mock_fetch.return_value = {"CID": 1}
        mock_cas.return_value = None

        enrich_product("test", catalog_number="CAT1")
        enrich_product("test", catalog_number="CAT1")

        assert mock_fetch.call_count == 1

    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_catalog_number_none_same_as_empty_string(self, mock_fetch):
        """Catalog number None produces same cache key as empty string."""
        mock_fetch.return_value = None

        enrich_product("test", catalog_number=None)
        # Second call without catalog_number should hit cache
        # because cache key is "test|" for both
        enrich_product("test")

        assert mock_fetch.call_count == 1

    @patch("lab_manager.services.pubchem._fetch_cas")
    @patch("lab_manager.services.pubchem._fetch_properties")
    def test_cas_failure_still_returns_props(self, mock_fetch, mock_cas):
        """Returns properties even when CAS fetch fails."""
        mock_fetch.return_value = {
            "CID": 2244,
            "MolecularWeight": "180.16",
            "MolecularFormula": "C6H12O6",
        }
        mock_cas.return_value = None

        result = enrich_product("glucose")

        assert result["pubchem_cid"] == 2244
        assert result["molecular_weight"] == 180.16
        assert "cas_number" not in result
