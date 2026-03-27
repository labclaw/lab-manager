"""Comprehensive unit tests for MSDS service (lab_manager.services.msds).

Tests all five functions: _extract_ghs_hazards, _classify_hazard,
_build_msds_url, lookup_msds, get_safety_alert with edge cases and
error paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from lab_manager.services.msds import (
    _HAZARD_KEYWORDS,
    _REVIEW_REQUIRED_CLASSES,
    _SAFETY_ALERTS,
    _SIGNAL_WORD_MAP,
    _build_msds_url,
    _classify_hazard,
    _extract_ghs_hazards,
    get_safety_alert,
    lookup_msds,
)


# =====================================================================
# _extract_ghs_hazards
# =====================================================================


class TestExtractGhsHazards:
    """Tests for _extract_ghs_hazards."""

    def test_typical_ghs_hazard_statement(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {
                                "sval": "H225: Highly Flammable liquid and vapour"
                            },
                        }
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == ["H225: Highly Flammable liquid and vapour"]

    def test_multiple_ghs_props(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": "H225: Highly Flammable"},
                        },
                        {
                            "urn": {"label": "GHS Hazard Classification"},
                            "value": {"sval": "Acute Tox. 4"},
                        },
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert len(result) == 2
        assert "H225: Highly Flammable" in result
        assert "Acute Tox. 4" in result

    def test_filters_out_non_ghs_props(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "Molecular Formula"},
                            "value": {"sval": "C2H6O"},
                        },
                        {
                            "urn": {"label": "Molecular Weight"},
                            "value": {"sval": "46.07"},
                        },
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_empty_sval_skipped(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": ""},
                        },
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_missing_value_key(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                        },
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_missing_sval_key(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"ival": 42},
                        },
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_empty_pc_compounds_raises_index_error(self):
        """Empty PC_Compounds list triggers IndexError (known edge case)."""
        data = {"PC_Compounds": []}
        with pytest.raises(IndexError):
            _extract_ghs_hazards(data)

    def test_missing_pc_compounds_key(self):
        data = {}
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_pc_compounds_first_entry_empty(self):
        data = {"PC_Compounds": [{}]}
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_pc_compounds_no_props_key(self):
        data = {"PC_Compounds": [{"id": {"id": {"cid": 702}}}]}
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_hazard_in_label_matched(self):
        """Props with 'Hazard' in label are also extracted."""
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "Hazard Identifier"},
                            "value": {"sval": "Skull and crossbones"},
                        },
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == ["Skull and crossbones"]

    def test_empty_props_list(self):
        data = {"PC_Compounds": [{"props": []}]}
        result = _extract_ghs_hazards(data)
        assert result == []

    def test_prop_missing_urn_key(self):
        data = {
            "PC_Compounds": [
                {
                    "props": [
                        {"value": {"sval": "some hazard"}},
                    ]
                }
            ]
        }
        result = _extract_ghs_hazards(data)
        assert result == []


# =====================================================================
# _classify_hazard
# =====================================================================


class TestClassifyHazard:
    """Tests for _classify_hazard."""

    def test_single_flammable(self):
        hazard_class, signal_word = _classify_hazard(["H225: Highly Flammable"])
        assert hazard_class == "Flammable"
        assert signal_word == "Warning"

    def test_single_toxic(self):
        hazard_class, signal_word = _classify_hazard(["H301: Toxic if swallowed"])
        assert "Acute Toxicity" in hazard_class
        assert signal_word == "Danger"

    def test_single_corrosive_abbreviation(self):
        hazard_class, signal_word = _classify_hazard(["Corros. 1B"])
        assert "Corrosive" in hazard_class
        assert signal_word == "Danger"

    def test_multiple_hazards_combined(self):
        hazard_class, signal_word = _classify_hazard(
            ["H225: Highly Flammable", "H301: Toxic if swallowed"]
        )
        assert "Flammable" in hazard_class
        assert "Acute Toxicity" in hazard_class
        assert signal_word == "Danger"

    def test_empty_list(self):
        hazard_class, signal_word = _classify_hazard([])
        assert hazard_class == ""
        assert signal_word == ""

    def test_unknown_hazard_keywords(self):
        """Hazards with no matching keyword produce empty result."""
        hazard_class, signal_word = _classify_hazard(["H333: Mild nuisance"])
        assert hazard_class == ""
        assert signal_word == ""

    def test_deduplication_of_hazard_classes(self):
        """Same class from two keywords should appear only once."""
        hazard_class, signal_word = _classify_hazard(
            ["Flammable liquid", "Flam. Solids"]
        )
        assert hazard_class == "Flammable"
        assert hazard_class.count("Flammable") == 1

    def test_carcinogenic_is_danger(self):
        hazard_class, signal_word = _classify_hazard(["Carcinogenic Category 1A"])
        assert "Carcinogenic" in hazard_class
        assert signal_word == "Danger"

    def test_stot_se_classification(self):
        hazard_class, signal_word = _classify_hazard(
            ["STOT SE 3: May cause drowsiness"]
        )
        assert "Specific Target Organ Toxicity (Single Exposure)" in hazard_class
        assert signal_word == "Danger"

    def test_stot_re_classification(self):
        hazard_class, signal_word = _classify_hazard(["STOT RE 2: Lungs"])
        assert "Specific Target Organ Toxicity (Repeated Exposure)" in hazard_class
        assert signal_word == "Danger"

    def test_reproductive_toxicity_abbreviation(self):
        hazard_class, signal_word = _classify_hazard(["Repr. 1B"])
        assert "Reproductive Toxicity" in hazard_class
        assert signal_word == "Danger"

    def test_mutagenic_abbreviation(self):
        hazard_class, signal_word = _classify_hazard(["Muta. 2"])
        assert "Mutagenic" in hazard_class
        assert signal_word == "Danger"

    def test_environmental_hazard(self):
        hazard_class, signal_word = _classify_hazard(["Aquatic Acute 1"])
        assert "Environmental Hazard" in hazard_class
        assert signal_word == "Warning"

    def test_aspiration_hazard(self):
        hazard_class, signal_word = _classify_hazard(["Aspiration Hazard Category 1"])
        assert "Aspiration Hazard" in hazard_class
        assert signal_word == "Danger"

    def test_compressed_gas(self):
        hazard_class, signal_word = _classify_hazard(["Gas under pressure"])
        assert "Compressed Gas" in hazard_class
        assert signal_word == "Warning"

    def test_oxidizer_abbreviation(self):
        hazard_class, signal_word = _classify_hazard(["Oxid. 1"])
        assert "Oxidizer" in hazard_class
        assert signal_word == "Danger"

    def test_eye_damage(self):
        hazard_class, signal_word = _classify_hazard(["Eye Damage Category 1"])
        assert "Eye Damage" in hazard_class
        assert signal_word == "Danger"

    def test_organic_peroxide(self):
        hazard_class, signal_word = _classify_hazard(["Organic peroxide Type B"])
        assert "Organic Peroxide" in hazard_class
        assert signal_word == "Danger"

    def test_pyrophoric(self):
        hazard_class, signal_word = _classify_hazard(["Pyrophoric liquid Category 1"])
        assert "Pyrophoric" in hazard_class
        assert signal_word == "Danger"

    def test_self_reactive(self):
        hazard_class, signal_word = _classify_hazard(["Self-reactive Type C"])
        assert "Self-reactive" in hazard_class
        assert signal_word == "Danger"

    def test_self_heating(self):
        hazard_class, signal_word = _classify_hazard(["Self-heating Category 2"])
        assert "Self-heating" in hazard_class
        assert signal_word == "Warning"

    def test_fatal_maps_to_acute_toxicity(self):
        hazard_class, signal_word = _classify_hazard(["Fatal if inhaled"])
        assert "Acute Toxicity" in hazard_class
        assert signal_word == "Danger"

    def test_skin_corrosion_maps_to_corrosive(self):
        hazard_class, signal_word = _classify_hazard(["Skin Corrosion 1A"])
        assert "Corrosive" in hazard_class
        assert signal_word == "Danger"

    def test_warning_only_classes(self):
        """When all classes map to Warning, signal word is Warning."""
        hazard_class, signal_word = _classify_hazard(
            ["Flammable", "Self-heating", "Compressed Gas"]
        )
        assert signal_word == "Warning"


# =====================================================================
# _build_msds_url
# =====================================================================


class TestBuildMsdsUrl:
    """Tests for _build_msds_url."""

    def test_valid_cid(self):
        assert _build_msds_url(702) == "https://pubchem.ncbi.nlm.nih.gov/compound/702"

    def test_none_cid(self):
        assert _build_msds_url(None) is None

    def test_zero_cid(self):
        assert _build_msds_url(0) == "https://pubchem.ncbi.nlm.nih.gov/compound/0"

    def test_large_cid(self):
        assert (
            _build_msds_url(123456789)
            == "https://pubchem.ncbi.nlm.nih.gov/compound/123456789"
        )


# =====================================================================
# lookup_msds
# =====================================================================


def _make_pubchem_response(
    cid=702,
    hazard_sval=None,
    extra_props=None,
):
    """Helper to build a PubChem-like JSON response."""
    props = []
    if hazard_sval:
        props.append(
            {
                "urn": {"label": "GHS Hazard Statement"},
                "value": {"sval": hazard_sval},
            }
        )
    if extra_props:
        props.extend(extra_props)
    return {
        "PC_Compounds": [
            {
                "id": {"id": {"cid": cid}},
                "props": props,
            }
        ]
    }


class TestLookupMsds:
    """Tests for lookup_msds."""

    @patch("lab_manager.services.msds.httpx.get")
    def test_successful_flammable_lookup(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_pubchem_response(
            cid=702, hazard_sval="H225: Highly Flammable liquid"
        )
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = lookup_msds("64-17-5")

        assert result["msds_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
        assert result["hazard_class"] == "Flammable"
        assert result["signal_word"] == "Warning"
        assert result["requires_safety_review"] is False

    @patch("lab_manager.services.msds.httpx.get")
    def test_successful_toxic_lookup_requires_review(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_pubchem_response(
            cid=750, hazard_sval="H301: Toxic if swallowed"
        )
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = lookup_msds("67-64-1")

        assert result["requires_safety_review"] is True
        assert result["signal_word"] == "Danger"
        assert "Acute Toxicity" in result["hazard_class"]

    @patch("lab_manager.services.msds.httpx.get")
    def test_404_compound_not_found(self, mock_get):
        resp = MagicMock()
        resp.status_code = 404
        mock_get.return_value = resp

        result = lookup_msds("00-00-0")

        assert result["msds_url"] is None
        assert result["hazard_class"] is None
        assert result["signal_word"] is None
        assert result["requires_safety_review"] is False

    @patch("lab_manager.services.msds.httpx.get")
    def test_429_rate_limit(self, mock_get):
        resp = MagicMock()
        resp.status_code = 429
        mock_get.return_value = resp

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None

    @patch("lab_manager.services.msds.httpx.get")
    def test_timeout_exception(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("Timeout")

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None
        assert result["hazard_class"] is None

    @patch("lab_manager.services.msds.httpx.get")
    def test_http_status_error(self, mock_get):
        resp = MagicMock()
        resp.status_code = 500
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=resp
        )
        mock_get.return_value = resp

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None

    @patch("lab_manager.services.msds.httpx.get")
    def test_generic_exception(self, mock_get):
        mock_get.side_effect = ConnectionError("Network down")

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None

    def test_empty_cas_string(self):
        result = lookup_msds("")
        assert result["msds_url"] is None
        assert result["hazard_class"] is None

    def test_whitespace_only_cas(self):
        result = lookup_msds("   ")
        assert result["msds_url"] is None

    def test_none_cas(self):
        result = lookup_msds(None)  # type: ignore[arg-type]
        assert result["msds_url"] is None

    @patch("lab_manager.services.msds.httpx.get")
    def test_no_hazard_data(self, mock_get):
        """Compound with no GHS hazard props."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 702}},
                    "props": [
                        {
                            "urn": {"label": "Molecular Formula"},
                            "value": {"sval": "C2H6O"},
                        }
                    ],
                }
            ]
        }
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = lookup_msds("64-17-5")

        assert result["msds_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
        assert result["hazard_class"] is None
        assert result["signal_word"] is None
        assert result["requires_safety_review"] is False

    @patch("lab_manager.services.msds.httpx.get")
    def test_no_cid_in_response(self, mock_get):
        """Response missing CID produces None msds_url."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "PC_Compounds": [
                {
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": "H225: Flammable"},
                        }
                    ]
                }
            ]
        }
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None
        assert result["hazard_class"] == "Flammable"

    @patch("lab_manager.services.msds.httpx.get")
    def test_empty_pc_compounds_in_response_raises(self, mock_get):
        """Empty PC_Compounds list triggers IndexError (outside try/except)."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"PC_Compounds": []}
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        with pytest.raises(IndexError):
            lookup_msds("64-17-5")

    @patch("lab_manager.services.msds.httpx.get")
    def test_cas_whitespace_trimmed(self, mock_get):
        """Leading/trailing whitespace in CAS is trimmed in URL."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_pubchem_response(cid=702)
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        lookup_msds("  64-17-5  ")

        call_args = mock_get.call_args
        assert "64-17-5" in call_args[0][0]
        assert "  64-17-5" not in call_args[0][0]

    @patch("lab_manager.services.msds.httpx.get")
    def test_multiple_hazards_requires_review(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_pubchem_response(
            cid=702,
            hazard_sval="H225: Flammable",
            extra_props=[
                {
                    "urn": {"label": "GHS Hazard Classification"},
                    "value": {"sval": "Carc. 1A"},
                },
            ],
        )
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = lookup_msds("64-17-5")

        assert result["requires_safety_review"] is True
        assert "Carcinogenic" in result["hazard_class"]
        assert "Flammable" in result["hazard_class"]
        assert result["signal_word"] == "Danger"

    @patch("lab_manager.services.msds.httpx.get")
    def test_timeout_value_passed(self, mock_get):
        """Verify the timeout parameter is passed to httpx.get."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_pubchem_response(cid=702)
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        lookup_msds("64-17-5")

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 5.0
        assert kwargs["follow_redirects"] is True

    @patch("lab_manager.services.msds.httpx.get")
    def test_connect_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None


# =====================================================================
# get_safety_alert
# =====================================================================


class TestGetSafetyAlert:
    """Tests for get_safety_alert."""

    def test_flammable_alert(self):
        alert = get_safety_alert("Ethanol", "Flammable")
        assert "fume hood" in alert
        assert "flammable cabinet" in alert.lower()

    def test_corrosive_alert(self):
        alert = get_safety_alert("HCl", "Corrosive")
        assert "gloves" in alert.lower()
        assert "goggles" in alert.lower()

    def test_pyrophoric_alert(self):
        alert = get_safety_alert("TBME", "Pyrophoric")
        assert "inert atmosphere" in alert.lower()

    def test_acute_toxicity_alert(self):
        alert = get_safety_alert("Arsenic", "Acute Toxicity")
        assert "fume hood" in alert.lower()
        assert "PPE" in alert

    def test_carcinogenic_alert(self):
        alert = get_safety_alert("Benzene", "Carcinogenic")
        assert "cancer" in alert.lower()

    def test_mutagenic_alert(self):
        alert = get_safety_alert("EMS", "Mutagenic")
        assert "genetic" in alert.lower()

    def test_reproductive_toxicity_alert(self):
        alert = get_safety_alert("Lead", "Reproductive Toxicity")
        assert "pregnant" in alert.lower()

    def test_oxidizer_alert(self):
        alert = get_safety_alert("KMnO4", "Oxidizer")
        assert "fire" in alert.lower()

    def test_compressed_gas_alert(self):
        alert = get_safety_alert("N2 Cylinder", "Compressed Gas")
        assert "cylinder" in alert.lower()

    def test_eye_damage_alert(self):
        alert = get_safety_alert("NaOH", "Eye Damage")
        assert "goggles" in alert.lower()

    def test_environmental_hazard_alert(self):
        alert = get_safety_alert("Pb(NO3)2", "Environmental Hazard")
        assert "aquatic" in alert.lower()

    def test_aspiration_hazard_alert(self):
        alert = get_safety_alert("Gasoline", "Aspiration Hazard")
        assert "vomiting" in alert.lower()

    def test_stot_se_alert(self):
        alert = get_safety_alert(
            "Chloroform", "Specific Target Organ Toxicity (Single Exposure)"
        )
        assert "STOT-SE" in alert

    def test_stot_re_alert(self):
        alert = get_safety_alert(
            "Silica", "Specific Target Organ Toxicity (Repeated Exposure)"
        )
        assert "STOT-RE" in alert

    def test_organic_peroxide_alert(self):
        alert = get_safety_alert("BPO", "Organic Peroxide")
        assert "explode" in alert.lower()

    def test_self_reactive_alert(self):
        alert = get_safety_alert("AIBN", "Self-reactive")
        assert "explosive" in alert.lower()

    def test_self_heating_alert(self):
        alert = get_safety_alert("Charcoal", "Self-heating")
        assert "cool" in alert.lower()

    def test_unknown_class_generic_message(self):
        alert = get_safety_alert("CustomChem", "CustomHazardType")
        assert "CustomChem" in alert
        assert "Safety Data Sheet" in alert

    def test_empty_class_no_data_message(self):
        alert = get_safety_alert("Water", "")
        assert "No specific safety data" in alert

    def test_none_class_no_data_message(self):
        alert = get_safety_alert("Salt", None)  # type: ignore[arg-type]
        assert "No specific safety data" in alert

    def test_multiple_classes_returns_last_known(self):
        """Multiple comma-separated classes: returns last known alert."""
        alert = get_safety_alert("ChemX", "Flammable, Corrosive")
        # Corrosive is last in reversed iteration => should match
        assert "gloves" in alert.lower() or "Corrosive" in alert

    def test_multiple_classes_first_unknown(self):
        """First class unknown, second known."""
        alert = get_safety_alert("ChemY", "UnknownHazard, Flammable")
        # Reversed iteration: checks Flammable first, then UnknownHazard
        assert "fume hood" in alert

    def test_all_classes_unknown(self):
        alert = get_safety_alert("ChemZ", "FooHazard, BarHazard")
        assert "ChemZ" in alert
        assert "Safety Data Sheet" in alert

    def test_whitespace_in_class_list(self):
        alert = get_safety_alert("ChemW", "  Flammable  ,  Corrosive  ")
        # After strip, both should be recognized
        assert "fume hood" in alert or "gloves" in alert.lower()


# =====================================================================
# Coverage of internal constants (light validation)
# =====================================================================


class TestInternalConstants:
    """Verify internal mapping constants are consistent."""

    def test_all_hazard_keywords_have_signal_word(self):
        """Every class in _HAZARD_KEYWORDS should have a signal word."""
        classes = set(_HAZARD_KEYWORDS.values())
        for cls in classes:
            assert cls in _SIGNAL_WORD_MAP, f"Missing signal word for {cls}"

    def test_all_signal_word_classes_have_alert(self):
        """Every class in _SIGNAL_WORD_MAP should have a safety alert."""
        for cls in _SIGNAL_WORD_MAP:
            assert cls in _SAFETY_ALERTS, f"Missing safety alert for {cls}"

    def test_review_classes_subset_of_signal_word_map(self):
        """All review-required classes should be in signal word map."""
        for cls in _REVIEW_REQUIRED_CLASSES:
            assert cls in _SIGNAL_WORD_MAP, f"Review class {cls} not in signal map"

    def test_review_classes_include_carcinogenic(self):
        assert "Carcinogenic" in _REVIEW_REQUIRED_CLASSES

    def test_review_classes_exclude_flammable(self):
        assert "Flammable" not in _REVIEW_REQUIRED_CLASSES
