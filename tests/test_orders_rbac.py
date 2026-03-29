"""Test orders GET endpoints require RBAC permission."""

from __future__ import annotations

from lab_manager.api.routes.orders import router


def _has_permission_dep(route) -> bool:
    dep_names = [str(d) for d in getattr(route, "dependencies", [])]
    return any("require_permission" in d for d in dep_names)


def test_list_orders_has_permission():
    """GET / must require view_orders permission."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == "/":
            if "GET" in getattr(route, "methods", set()):
                assert _has_permission_dep(route), "list_orders missing RBAC"
                return
    raise AssertionError("GET / route not found")


def test_get_order_has_permission():
    """GET /{order_id} must require view_orders permission."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == "/{order_id}":
            if "GET" in getattr(route, "methods", set()):
                assert _has_permission_dep(route), "get_order missing RBAC"
                return
    raise AssertionError("GET /{order_id} route not found")


def test_list_order_items_has_permission():
    """GET /{order_id}/items must require view_orders permission."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == "/{order_id}/items":
            if "GET" in getattr(route, "methods", set()):
                assert _has_permission_dep(route), "list_order_items missing RBAC"
                return
    raise AssertionError("GET /{order_id}/items route not found")


def test_get_order_item_has_permission():
    """GET /{order_id}/items/{item_id} must require view_orders permission."""
    for route in router.routes:
        if hasattr(route, "path") and route.path == "/{order_id}/items/{item_id}":
            if "GET" in getattr(route, "methods", set()):
                assert _has_permission_dep(route), "get_order_item missing RBAC"
                return
    raise AssertionError("GET /{order_id}/items/{item_id} route not found")
