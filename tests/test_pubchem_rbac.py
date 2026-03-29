"""Test PubChem endpoints require RBAC permission."""

from __future__ import annotations

from lab_manager.api.routes.products import router


def test_pubchem_get_has_permission_dependency():
    """GET /{product_id}/pubchem must require manage_products permission."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == "/{product_id}/pubchem":
            if "GET" in getattr(route, "methods", set()):
                dep_names = [str(d) for d in getattr(route, "dependencies", [])]
                assert any("require_permission" in d for d in dep_names), (
                    "GET /pubchem missing require_permission dependency"
                )
                return
    raise AssertionError("GET /{product_id}/pubchem route not found")


def test_enrich_post_has_permission_dependency():
    """POST /{product_id}/enrich must require manage_products permission."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == "/{product_id}/enrich":
            if "POST" in getattr(route, "methods", set()):
                dep_names = [str(d) for d in getattr(route, "dependencies", [])]
                assert any("require_permission" in d for d in dep_names), (
                    "POST /enrich missing require_permission dependency"
                )
                return
    raise AssertionError("POST /{product_id}/enrich route not found")
