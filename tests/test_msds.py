"""Tests for MSDS auto-linking service and API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


class TestMSDSService:
    """Unit tests for lab_manager.services.msds."""

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_success(self, mock_get):
        """Given a CAS number with GHS data, returns full MSDS info."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 702}},
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {
                                "sval": "H225: Highly Flammable liquid and vapour"
                            },
                        },
                        {
                            "urn": {"label": "GHS Precaution Statement"},
                            "value": {"sval": "P210: Keep away from heat"},
                        },
                    ],
                }
            ]
        }
        response.raise_for_status = MagicMock()
        mock_get.return_value = response

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("64-17-5")

        assert result["msds_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
        assert result["hazard_class"] == "Flammable"
        assert result["signal_word"] == "Warning"
        assert result["requires_safety_review"] is False

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_dangerous_chemical(self, mock_get):
        """Dangerous chemicals require safety review."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 750}},
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": "H301: Toxic if swallowed"},
                        },
                    ],
                }
            ]
        }
        response.raise_for_status = MagicMock()
        mock_get.return_value = response

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("67-64-1")

        assert result["requires_safety_review"] is True
        assert result["signal_word"] == "Danger"
        assert "Acute Toxicity" in result["hazard_class"]

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_not_found(self, mock_get):
        """Given an unknown CAS, returns empty-valued result."""
        response = MagicMock()
        response.status_code = 404
        mock_get.return_value = response

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("00-00-0")

        assert result["msds_url"] is None
        assert result["hazard_class"] is None
        assert result["signal_word"] is None
        assert result["requires_safety_review"] is False

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_timeout(self, mock_get):
        """Given a timeout, returns empty-valued result."""
        mock_get.side_effect = httpx.TimeoutException("Timeout")

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("64-17-5")

        assert result["msds_url"] is None

    def test_lookup_msds_empty_cas(self):
        """Empty CAS number returns empty-valued result without HTTP call."""
        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("")
        assert result["msds_url"] is None
        assert result["hazard_class"] is None

    def test_lookup_msds_none_cas(self):
        """None CAS number returns empty-valued result."""
        from lab_manager.services.msds import lookup_msds

        result = lookup_msds(None)  # type: ignore[arg-type]
        assert result["msds_url"] is None

    def test_safety_alert_flammable(self):
        """Flammable hazard returns correct safety alert."""
        from lab_manager.services.msds import get_safety_alert

        alert = get_safety_alert("Ethanol", "Flammable")
        assert "fume hood" in alert
        assert "ignition" in alert.lower()

    def test_safety_alert_corrosive(self):
        """Corrosive hazard returns correct safety alert."""
        from lab_manager.services.msds import get_safety_alert

        alert = get_safety_alert("HCl", "Corrosive")
        assert "gloves" in alert.lower()
        assert "goggles" in alert.lower()

    def test_safety_alert_unknown_class(self):
        """Unknown hazard class returns generic safety message."""
        from lab_manager.services.msds import get_safety_alert

        alert = get_safety_alert("CustomChem", "CustomHazardType")
        assert "CustomChem" in alert
        assert "Safety Data Sheet" in alert

    def test_safety_alert_empty_class(self):
        """Empty hazard class returns no-safety-data message."""
        from lab_manager.services.msds import get_safety_alert

        alert = get_safety_alert("Water", "")
        assert "No specific safety data" in alert

    def test_safety_alert_multiple_classes(self):
        """Multiple hazard classes returns the most severe alert."""
        from lab_manager.services.msds import get_safety_alert

        alert = get_safety_alert("TestChem", "Flammable, Corrosive")
        # Corrosive is last/more severe, should be returned
        assert "Corrosive" in alert or "gloves" in alert.lower()

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_rate_limit(self, mock_get):
        """429 response returns empty-valued result."""
        response = MagicMock()
        response.status_code = 429
        mock_get.return_value = response

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("64-17-5")
        assert result["msds_url"] is None

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_multiple_hazards(self, mock_get):
        """Multiple GHS hazards are combined into comma-separated classes."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 702}},
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": "H225: Highly Flammable liquid"},
                        },
                        {
                            "urn": {"label": "GHS Hazard Classification"},
                            "value": {"sval": "Acute Tox. 4"},
                        },
                    ],
                }
            ]
        }
        response.raise_for_status = MagicMock()
        mock_get.return_value = response

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("64-17-5")

        assert "Flammable" in result["hazard_class"]
        assert "Acute Toxicity" in result["hazard_class"]
        assert result["signal_word"] == "Danger"

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_server_error(self, mock_get):
        """500 server error returns empty-valued result."""
        response = MagicMock()
        response.status_code = 500
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response
        )
        mock_get.return_value = response

        from lab_manager.services.msds import lookup_msds

        result = lookup_msds("64-17-5")
        assert result["msds_url"] is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestMSDSEndpoints:
    """Integration tests for /api/v1/products/{id}/msds and /lookup-msds."""

    def _create_product(self, client, name="Ethanol", cas_number="64-17-5"):
        resp = client.post(
            "/api/v1/products/",
            json={
                "name": name,
                "catalog_number": "E7023",
                "cas_number": cas_number,
            },
        )
        assert resp.status_code == 201
        return resp.json()

    def _create_product_no_cas(self, client, name="Unknown Chem"):
        resp = client.post(
            "/api/v1/products/",
            json={"name": name, "catalog_number": "UC001"},
        )
        assert resp.status_code == 201
        return resp.json()

    def test_product_response_includes_msds_fields(self, client):
        """Product response includes MSDS fields."""
        product = self._create_product(client)
        resp = client.get(f"/api/v1/products/{product['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "hazard_class" in data
        assert "msds_url" in data
        assert "requires_safety_review" in data

    def test_msds_endpoint_no_cas(self, client):
        """GET /msds for product without CAS returns defaults."""
        product = self._create_product_no_cas(client)
        resp = client.get(f"/api/v1/products/{product['id']}/msds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cas_number"] is None
        assert data["msds_url"] is None
        assert data["hazard_class"] is None

    @patch("lab_manager.services.msds.httpx.get")
    def test_msds_endpoint_auto_lookup(self, mock_get, client):
        """GET /msds auto-looks up when CAS exists but no MSDS data."""
        product = self._create_product(client)

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 702}},
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": "H225: Highly Flammable liquid"},
                        },
                    ],
                }
            ]
        }
        response.raise_for_status = MagicMock()
        mock_get.return_value = response

        resp = client.get(f"/api/v1/products/{product['id']}/msds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["msds_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
        assert data["hazard_class"] == "Flammable"
        assert data["safety_alert"] is not None
        assert "fume hood" in data["safety_alert"]

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_endpoint_persists(self, mock_get, client):
        """POST /lookup-msds persists MSDS data to product record."""
        product = self._create_product(client)

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 702}},
                    "props": [
                        {
                            "urn": {"label": "GHS Hazard Statement"},
                            "value": {"sval": "H225: Highly Flammable liquid"},
                        },
                    ],
                }
            ]
        }
        response.raise_for_status = MagicMock()
        mock_get.return_value = response

        resp = client.post(f"/api/v1/products/{product['id']}/lookup-msds")
        assert resp.status_code == 200
        data = resp.json()
        assert data["msds_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"
        assert data["hazard_class"] == "Flammable"

        # Verify persistence
        resp2 = client.get(f"/api/v1/products/{product['id']}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["msds_url"] == "https://pubchem.ncbi.nlm.nih.gov/compound/702"

    def test_lookup_msds_endpoint_no_cas_fails(self, client):
        """POST /lookup-msds for product without CAS returns 422."""
        product = self._create_product_no_cas(client)
        resp = client.post(f"/api/v1/products/{product['id']}/lookup-msds")
        assert resp.status_code == 422

    def test_msds_endpoint_product_not_found(self, client):
        """GET /products/99999/msds returns 404."""
        resp = client.get("/api/v1/products/99999/msds")
        assert resp.status_code == 404

    def test_lookup_msds_endpoint_product_not_found(self, client):
        """POST /products/99999/lookup-msds returns 404."""
        resp = client.post("/api/v1/products/99999/lookup-msds")
        assert resp.status_code == 404

    @patch("lab_manager.services.msds.httpx.get")
    def test_lookup_msds_does_not_overwrite_existing(self, mock_get, client):
        """POST /lookup-msds preserves manually-set msds_url."""
        product = self._create_product(client)

        # Manually set msds_url first
        client.patch(
            f"/api/v1/products/{product['id']}",
            json={"msds_url": "https://example.com/manual-sds.pdf"},
        )

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "PC_Compounds": [
                {
                    "id": {"id": {"cid": 702}},
                    "props": [],
                }
            ]
        }
        response.raise_for_status = MagicMock()
        mock_get.return_value = response

        resp = client.post(f"/api/v1/products/{product['id']}/lookup-msds")
        assert resp.status_code == 200
        data = resp.json()
        # Should keep the manually-set URL
        assert data["msds_url"] == "https://example.com/manual-sds.pdf"

    def test_cas_number_stores_correctly(self, client):
        """CAS number field stores and retrieves correctly."""
        resp = client.post(
            "/api/v1/products/",
            json={
                "name": "Acetone",
                "catalog_number": "ACE001",
                "cas_number": "67-64-1",
            },
        )
        assert resp.status_code == 201
        product = resp.json()
        assert product["cas_number"] == "67-64-1"

        # Retrieve to confirm persistence
        resp2 = client.get(f"/api/v1/products/{product['id']}")
        assert resp2.status_code == 200
        assert resp2.json()["cas_number"] == "67-64-1"

    def test_product_create_with_msds_fields(self, client):
        """Product can be created with MSDS fields via PATCH."""
        resp = client.post(
            "/api/v1/products/",
            json={"name": "TestChem", "catalog_number": "TC001"},
        )
        assert resp.status_code == 201
        product = resp.json()

        # Patch MSDS fields
        resp2 = client.patch(
            f"/api/v1/products/{product['id']}",
            json={
                "hazard_class": "Flammable, Corrosive",
                "requires_safety_review": True,
            },
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["hazard_class"] == "Flammable, Corrosive"
        assert data["requires_safety_review"] is True
