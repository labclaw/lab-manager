"""Tests for PubChem enrichment service and API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx


# ---------------------------------------------------------------------------
# Service-layer tests (mock HTTP)
# ---------------------------------------------------------------------------


class TestPubChemService:
    """Unit tests for lab_manager.services.pubchem."""

    def setup_method(self):
        from lab_manager.services.pubchem import clear_cache

        clear_cache()

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_success(self, mock_get):
        """Given a valid compound name, enrich_product returns all fields."""
        props_response = MagicMock()
        props_response.status_code = 200
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "MolecularWeight": 46.07,
                        "MolecularFormula": "C2H6O",
                        "CanonicalSMILES": "CCO",
                        "IUPACName": "ethanol",
                    }
                ]
            }
        }
        props_response.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [
                    {
                        "CID": 702,
                        "Synonym": ["Ethanol", "64-17-5", "Ethyl alcohol"],
                    }
                ]
            }
        }

        mock_get.side_effect = [props_response, synonyms_response]

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("ethanol")

        assert result["pubchem_cid"] == 702
        assert result["molecular_weight"] == 46.07
        assert result["molecular_formula"] == "C2H6O"
        assert result["smiles"] == "CCO"
        assert result["iupac_name"] == "ethanol"
        assert result["cas_number"] == "64-17-5"

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_not_found(self, mock_get):
        """Given an unknown compound, enrich_product returns empty dict."""
        response = MagicMock()
        response.status_code = 404
        mock_get.return_value = response

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("nonexistent_compound_xyz_12345")

        assert result == {}

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_timeout(self, mock_get):
        """Given a timeout from PubChem, enrich_product returns empty dict."""
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("ethanol")

        assert result == {}

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_rate_limit(self, mock_get):
        """Given a 429 from PubChem, enrich_product returns empty dict."""
        response = MagicMock()
        response.status_code = 429
        mock_get.return_value = response

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("ethanol")

        assert result == {}

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_caching(self, mock_get):
        """Second call with same args returns cached result without HTTP."""
        props_response = MagicMock()
        props_response.status_code = 200
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "MolecularWeight": 46.07,
                        "MolecularFormula": "C2H6O",
                        "CanonicalSMILES": "CCO",
                        "IUPACName": "ethanol",
                    }
                ]
            }
        }
        props_response.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {"Information": [{"CID": 702, "Synonym": ["64-17-5"]}]}
        }

        mock_get.side_effect = [props_response, synonyms_response]

        from lab_manager.services.pubchem import enrich_product

        result1 = enrich_product("ethanol")
        result2 = enrich_product("ethanol")

        assert result1 == result2
        # Only 2 HTTP calls (properties + synonyms), not 4
        assert mock_get.call_count == 2

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_fallback_to_catalog_number(self, mock_get):
        """When name lookup fails, falls back to catalog_number."""
        not_found = MagicMock()
        not_found.status_code = 404

        found = MagicMock()
        found.status_code = 200
        found.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 999,
                        "MolecularWeight": 100.0,
                        "MolecularFormula": "C5H10",
                        "CanonicalSMILES": "CCCCC",
                        "IUPACName": "pentane",
                    }
                ]
            }
        }
        found.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {"Information": [{"CID": 999, "Synonym": ["109-66-0"]}]}
        }

        # First call (by name) returns 404, second (by catalog) returns result
        mock_get.side_effect = [not_found, found, synonyms_response]

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("unknown-brand-name", catalog_number="pentane")

        assert result["pubchem_cid"] == 999
        assert result["molecular_formula"] == "C5H10"

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_no_cas_in_synonyms(self, mock_get):
        """When no CAS pattern found in synonyms, cas_number is absent."""
        props_response = MagicMock()
        props_response.status_code = 200
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 100,
                        "MolecularWeight": 50.0,
                        "MolecularFormula": "CH4",
                        "CanonicalSMILES": "C",
                        "IUPACName": "methane",
                    }
                ]
            }
        }
        props_response.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{"CID": 100, "Synonym": ["Methane", "Natural gas"]}]
            }
        }

        mock_get.side_effect = [props_response, synonyms_response]

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("methane")

        assert "cas_number" not in result
        assert result["pubchem_cid"] == 100

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_product_http_error(self, mock_get):
        """Given a 500 server error, enrich_product returns empty dict."""
        response = MagicMock()
        response.status_code = 500
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response
        )
        mock_get.return_value = response

        from lab_manager.services.pubchem import enrich_product

        result = enrich_product("ethanol")

        assert result == {}


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestPubChemEndpoints:
    """Integration tests for /api/v1/products/{id}/pubchem and /enrich."""

    def _create_product(self, client, name="Ethanol", catalog_number="E7023"):
        resp = client.post(
            "/api/v1/products/",
            json={"name": name, "catalog_number": catalog_number},
        )
        assert resp.status_code == 201
        return resp.json()

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_get_pubchem_endpoint(self, mock_get, client):
        """GET /products/{id}/pubchem returns enrichment data."""
        product = self._create_product(client)

        props_response = MagicMock()
        props_response.status_code = 200
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "MolecularWeight": 46.07,
                        "MolecularFormula": "C2H6O",
                        "CanonicalSMILES": "CCO",
                        "IUPACName": "ethanol",
                    }
                ]
            }
        }
        props_response.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {"Information": [{"CID": 702, "Synonym": ["64-17-5"]}]}
        }

        mock_get.side_effect = [props_response, synonyms_response]

        from lab_manager.services.pubchem import clear_cache

        clear_cache()

        resp = client.get(f"/api/v1/products/{product['id']}/pubchem")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == product["id"]
        assert data["enrichment"]["pubchem_cid"] == 702

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_endpoint_persists(self, mock_get, client):
        """POST /products/{id}/enrich writes enrichment data to DB."""
        product = self._create_product(client)

        props_response = MagicMock()
        props_response.status_code = 200
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "MolecularWeight": 46.07,
                        "MolecularFormula": "C2H6O",
                        "CanonicalSMILES": "CCO",
                        "IUPACName": "ethanol",
                    }
                ]
            }
        }
        props_response.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {"Information": [{"CID": 702, "Synonym": ["64-17-5"]}]}
        }

        mock_get.side_effect = [props_response, synonyms_response]

        from lab_manager.services.pubchem import clear_cache

        clear_cache()

        resp = client.post(f"/api/v1/products/{product['id']}/enrich")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pubchem_cid"] == 702
        assert data["molecular_weight"] == 46.07
        assert data["molecular_formula"] == "C2H6O"
        assert data["smiles"] == "CCO"
        assert data["cas_number"] == "64-17-5"

        # Verify data persisted by re-fetching the product
        resp2 = client.get(f"/api/v1/products/{product['id']}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["pubchem_cid"] == 702

    @patch("lab_manager.services.pubchem.httpx.get")
    def test_enrich_does_not_overwrite_existing(self, mock_get, client):
        """POST /products/{id}/enrich preserves manually-set CAS number."""
        product = self._create_product(client)

        # Manually set CAS number first
        client.patch(
            f"/api/v1/products/{product['id']}",
            json={"cas_number": "99-99-9"},
        )

        props_response = MagicMock()
        props_response.status_code = 200
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 702,
                        "MolecularWeight": 46.07,
                        "MolecularFormula": "C2H6O",
                        "CanonicalSMILES": "CCO",
                        "IUPACName": "ethanol",
                    }
                ]
            }
        }
        props_response.raise_for_status = MagicMock()

        synonyms_response = MagicMock()
        synonyms_response.status_code = 200
        synonyms_response.json.return_value = {
            "InformationList": {"Information": [{"CID": 702, "Synonym": ["64-17-5"]}]}
        }

        mock_get.side_effect = [props_response, synonyms_response]

        from lab_manager.services.pubchem import clear_cache

        clear_cache()

        resp = client.post(f"/api/v1/products/{product['id']}/enrich")
        assert resp.status_code == 200
        data = resp.json()
        # CAS should remain the manually-set value, not overwritten
        assert data["cas_number"] == "99-99-9"
        # But other fields should be filled
        assert data["molecular_weight"] == 46.07

    def test_pubchem_endpoint_product_not_found(self, client):
        """GET /products/99999/pubchem returns 404 for missing product."""
        resp = client.get("/api/v1/products/99999/pubchem")
        assert resp.status_code == 404

    def test_enrich_endpoint_product_not_found(self, client):
        """POST /products/99999/enrich returns 404 for missing product."""
        resp = client.post("/api/v1/products/99999/enrich")
        assert resp.status_code == 404
