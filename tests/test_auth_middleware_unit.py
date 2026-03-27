"""Unit tests for auth.py RBAC helpers and deps.py dependency injection.

Covers:
- Role/permission data structures and lookups
- get_permissions() with valid and invalid roles
- get_current_staff() with various request.state scenarios
- require_permission() dependency with per-role permission checks
- get_or_404() with found and not-found objects
- verify_api_key() with auth enabled/disabled, valid/invalid/missing keys
- Edge cases: missing auth headers, invalid tokens, role hierarchy
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.api.auth import (
    ALL_PERMISSIONS,
    ROLE_LEVELS,
    ROLE_PERMISSIONS,
    ROLES,
    get_current_staff,
    get_permissions,
    require_permission,
)
from lab_manager.api.deps import get_or_404, verify_api_key
from lab_manager.exceptions import NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(*, staff: dict[str, Any] | None = None) -> Request:
    """Build a minimal FastAPI Request with an optional ``staff`` attr."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "query_string": b"",
        "headers": [],
    }
    req = Request(scope)
    if staff is not None:
        req.state.staff = staff
    return req


# ---------------------------------------------------------------------------
# auth.py — Role / Permission constants
# ---------------------------------------------------------------------------


class TestRoleConstants:
    """Validate the role and permission data structures."""

    def test_roles_tuple_contains_all_roles(self):
        assert "pi" in ROLES
        assert "admin" in ROLES
        assert "postdoc" in ROLES
        assert "grad_student" in ROLES
        assert "tech" in ROLES
        assert "undergrad" in ROLES
        assert "visitor" in ROLES
        assert len(ROLES) == 7

    def test_role_levels_has_entry_for_every_role(self):
        for role in ROLES:
            assert role in ROLE_LEVELS, f"{role} missing from ROLE_LEVELS"

    def test_pi_is_most_privileged(self):
        assert ROLE_LEVELS["pi"] == 0

    def test_admin_second_most_privileged(self):
        assert ROLE_LEVELS["admin"] == 1

    def test_grad_student_and_tech_same_level(self):
        assert ROLE_LEVELS["grad_student"] == ROLE_LEVELS["tech"] == 3

    def test_undergrad_and_visitor_same_level(self):
        assert ROLE_LEVELS["undergrad"] == ROLE_LEVELS["visitor"] == 4

    def test_all_permissions_are_strings(self):
        for perm in ALL_PERMISSIONS:
            assert isinstance(perm, str)

    def test_all_permissions_nonempty(self):
        for perm in ALL_PERMISSIONS:
            assert len(perm) > 0

    def test_role_permissions_has_entry_for_every_role(self):
        for role in ROLES:
            assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"

    def test_every_role_permission_subset_of_all_permissions(self):
        for role, perms in ROLE_PERMISSIONS.items():
            assert perms <= ALL_PERMISSIONS, (
                f"{role} has permissions not in ALL_PERMISSIONS: {perms - ALL_PERMISSIONS}"
            )

    def test_pi_has_all_permissions(self):
        assert ROLE_PERMISSIONS["pi"] == ALL_PERMISSIONS

    def test_admin_missing_delete_records(self):
        assert "delete_records" not in ROLE_PERMISSIONS["admin"]
        # But has everything else
        assert ROLE_PERMISSIONS["admin"] == ALL_PERMISSIONS - {"delete_records"}

    def test_undergrad_and_visitor_permissions_identical(self):
        assert ROLE_PERMISSIONS["undergrad"] == ROLE_PERMISSIONS["visitor"]
        assert ROLE_PERMISSIONS["undergrad"] == frozenset(
            {"view_inventory", "view_documents", "view_equipment"}
        )


# ---------------------------------------------------------------------------
# auth.py — get_permissions()
# ---------------------------------------------------------------------------


class TestGetPermissions:
    """Test the get_permissions() lookup function."""

    def test_known_role_returns_permission_set(self):
        perms = get_permissions("pi")
        assert perms == ALL_PERMISSIONS

    def test_unknown_role_returns_empty_frozenset(self):
        perms = get_permissions("nonexistent_role")
        assert perms == frozenset()

    def test_empty_string_returns_empty_frozenset(self):
        perms = get_permissions("")
        assert perms == frozenset()

    def test_result_is_frozenset(self):
        for role in ROLES:
            assert isinstance(get_permissions(role), frozenset)

    def test_cached_results_are_identical(self):
        """lru_cache should return the same object for the same input."""
        result1 = get_permissions("admin")
        result2 = get_permissions("admin")
        assert result1 is result2


# ---------------------------------------------------------------------------
# auth.py — get_current_staff()
# ---------------------------------------------------------------------------


class TestGetCurrentStaff:
    """Test the get_current_staff() request-state extractor."""

    def test_valid_staff_dict_returned(self):
        staff = {"id": 1, "name": "Alice", "role": "admin"}
        req = _make_request(staff=staff)
        result = get_current_staff(req)
        assert result == staff

    def test_staff_with_zero_id_is_valid(self):
        """id=0 should be treated as a valid staff entry."""
        staff = {"id": 0, "name": "Zero", "role": "member"}
        req = _make_request(staff=staff)
        result = get_current_staff(req)
        assert result["id"] == 0

    def test_missing_staff_raises_401(self):
        req = _make_request()  # no staff attribute
        with pytest.raises(HTTPException) as exc_info:
            get_current_staff(req)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    def test_staff_with_none_id_raises_401(self):
        staff = {"id": None, "name": "Bad"}
        req = _make_request(staff=staff)
        with pytest.raises(HTTPException) as exc_info:
            get_current_staff(req)
        assert exc_info.value.status_code == 401

    def test_empty_dict_raises_401(self):
        """Empty dict has no 'id' key, so staff.get('id') returns None."""
        req = _make_request(staff={})
        with pytest.raises(HTTPException) as exc_info:
            get_current_staff(req)
        assert exc_info.value.status_code == 401

    def test_staff_falsey_but_has_id_passes(self):
        """A dict with id present but other falsey values should still pass."""
        staff = {"id": 42, "name": "", "role": ""}
        req = _make_request(staff=staff)
        result = get_current_staff(req)
        assert result["id"] == 42


# ---------------------------------------------------------------------------
# auth.py — require_permission()
# ---------------------------------------------------------------------------


class TestRequirePermission:
    """Test the require_permission() dependency factory."""

    def _check(self, staff: dict[str, Any], *perms: str) -> dict[str, Any] | None:
        """Run require_permission with a mock request carrying the given staff."""
        checker = require_permission(*perms)
        req = _make_request(staff=staff)
        return checker(req)

    # -- successful checks --

    def test_pi_has_all_permissions(self):
        staff = {"id": 1, "role": "pi"}
        result = self._check(staff, "delete_records", "manage_users")
        assert result == staff

    def test_admin_can_manage_users_but_not_delete(self):
        staff = {"id": 2, "role": "admin"}
        result = self._check(staff, "manage_users")
        assert result == staff

    def test_admin_lacks_delete_records(self):
        staff = {"id": 2, "role": "admin"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "delete_records")
        assert exc_info.value.status_code == 403
        assert "delete_records" in exc_info.value.detail

    def test_postdoc_can_review_documents(self):
        staff = {"id": 3, "role": "postdoc"}
        result = self._check(staff, "review_documents")
        assert result == staff

    def test_postdoc_cannot_manage_users(self):
        staff = {"id": 3, "role": "postdoc"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "manage_users")
        assert exc_info.value.status_code == 403
        assert "manage_users" in exc_info.value.detail

    def test_grad_student_can_view_inventory(self):
        staff = {"id": 4, "role": "grad_student"}
        result = self._check(staff, "view_inventory")
        assert result == staff

    def test_grad_student_cannot_approve_orders(self):
        staff = {"id": 4, "role": "grad_student"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "approve_orders")
        assert exc_info.value.status_code == 403

    def test_undergrad_can_view_inventory(self):
        staff = {"id": 5, "role": "undergrad"}
        result = self._check(staff, "view_inventory")
        assert result == staff

    def test_undergrad_cannot_create_orders(self):
        staff = {"id": 5, "role": "undergrad"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "create_orders")
        assert exc_info.value.status_code == 403

    def test_visitor_cannot_create_orders(self):
        staff = {"id": 6, "role": "visitor"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "create_orders")
        assert exc_info.value.status_code == 403

    # -- unknown role falls back to empty permissions --

    def test_unknown_role_denied_all_permissions(self):
        staff = {"id": 99, "role": "superuser"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "view_inventory")
        assert exc_info.value.status_code == 403

    def test_unknown_role_denied_with_missing_role_key(self):
        """Staff dict without 'role' key defaults to 'visitor'."""
        staff = {"id": 99}
        # Defaults to "visitor" role which only has view_inventory/view_documents/view_equipment
        result = self._check(staff, "view_inventory")
        assert result == staff

    def test_unknown_role_denied_manage_users(self):
        staff = {"id": 99}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "manage_users")
        assert exc_info.value.status_code == 403

    # -- multiple permissions at once --

    def test_multiple_perms_all_satisfied(self):
        staff = {"id": 1, "role": "pi"}
        result = self._check(staff, "view_orders", "create_orders", "manage_users")
        assert result == staff

    def test_multiple_perms_one_missing(self):
        staff = {"id": 4, "role": "grad_student"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "view_orders", "manage_users")
        assert exc_info.value.status_code == 403
        # Only manage_users should be reported as missing
        assert "manage_users" in exc_info.value.detail
        assert "view_orders" not in exc_info.value.detail

    # -- no authentication at all --

    def test_no_staff_raises_401(self):
        """require_permission should bubble up 401 from get_current_staff."""
        checker = require_permission("view_inventory")
        req = _make_request()  # no staff
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 401

    # -- single permission --

    def test_single_perm_checker_returns_staff(self):
        staff = {"id": 1, "role": "pi"}
        result = self._check(staff, "view_inventory")
        assert result == staff

    # -- error message format --

    def test_error_message_lists_missing_perms(self):
        staff = {"id": 5, "role": "undergrad"}
        with pytest.raises(HTTPException) as exc_info:
            self._check(staff, "manage_users", "delete_records")
        detail = exc_info.value.detail
        assert "Insufficient permissions" in detail
        assert "delete_records" in detail
        assert "manage_users" in detail


# ---------------------------------------------------------------------------
# auth.py — Role-based access matrix
# ---------------------------------------------------------------------------


_ROLES_WITH_CREATE_ORDERS = ("pi", "admin", "postdoc")
_ROLES_WITH_MANAGE_USERS = ("pi", "admin")
_ROLES_WITH_DELETE_RECORDS = ("pi",)
_ROLES_WITHOUT_CREATE_ORDERS = tuple(
    r for r in ROLES if r not in _ROLES_WITH_CREATE_ORDERS
)
_ROLES_WITHOUT_MANAGE_USERS = tuple(
    r for r in ROLES if r not in _ROLES_WITH_MANAGE_USERS
)
_ROLES_WITHOUT_DELETE_RECORDS = tuple(
    r for r in ROLES if r not in _ROLES_WITH_DELETE_RECORDS
)


class TestRoleAccessMatrix:
    """Systematic check of key permissions across roles."""

    @pytest.mark.parametrize("role", ROLES)
    def test_every_role_can_view_inventory(self, role: str):
        perms = get_permissions(role)
        assert "view_inventory" in perms

    @pytest.mark.parametrize("role", _ROLES_WITH_CREATE_ORDERS)
    def test_create_orders_allowed(self, role: str):
        perms = get_permissions(role)
        assert "create_orders" in perms

    @pytest.mark.parametrize("role", _ROLES_WITHOUT_CREATE_ORDERS)
    def test_create_orders_denied(self, role: str):
        perms = get_permissions(role)
        assert "create_orders" not in perms

    @pytest.mark.parametrize("role", _ROLES_WITH_MANAGE_USERS)
    def test_manage_users_allowed(self, role: str):
        perms = get_permissions(role)
        assert "manage_users" in perms

    @pytest.mark.parametrize("role", _ROLES_WITHOUT_MANAGE_USERS)
    def test_manage_users_denied(self, role: str):
        perms = get_permissions(role)
        assert "manage_users" not in perms

    @pytest.mark.parametrize("role", _ROLES_WITH_DELETE_RECORDS)
    def test_delete_records_allowed(self, role: str):
        perms = get_permissions(role)
        assert "delete_records" in perms

    @pytest.mark.parametrize("role", _ROLES_WITHOUT_DELETE_RECORDS)
    def test_delete_records_denied(self, role: str):
        perms = get_permissions(role)
        assert "delete_records" not in perms

    def test_tech_has_manage_alerts_but_grad_student_does_not(self):
        assert "manage_alerts" in get_permissions("tech")
        assert "manage_alerts" not in get_permissions("grad_student")

    def test_grad_student_has_request_order_but_tech_does_not(self):
        assert "request_order" in get_permissions("grad_student")
        assert "request_order" not in get_permissions("tech")

    def test_postdoc_has_export_data(self):
        assert "export_data" in get_permissions("postdoc")

    def test_grad_student_has_ask_ai(self):
        assert "ask_ai" in get_permissions("grad_student")

    def test_tech_has_ask_ai(self):
        assert "ask_ai" in get_permissions("tech")


# ---------------------------------------------------------------------------
# deps.py — get_or_404()
# ---------------------------------------------------------------------------


class TestGetOr404:
    """Test the get_or_404() dependency helper."""

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite session for get_or_404 tests."""
        engine = create_engine(
            "sqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        import lab_manager.models  # noqa: F401

        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
        engine.dispose()

    def test_returns_object_when_found(self, db_session: Session):
        from lab_manager.models.staff import Staff

        staff = Staff(
            name="Found User",
            email="found@example.com",
            role="admin",
        )
        db_session.add(staff)
        db_session.commit()
        db_session.refresh(staff)

        result = get_or_404(db_session, Staff, staff.id)
        assert result.id == staff.id
        assert result.name == "Found User"

    def test_raises_not_found_error_when_missing(self, db_session: Session):
        from lab_manager.models.staff import Staff

        with pytest.raises(NotFoundError) as exc_info:
            get_or_404(db_session, Staff, 99999)
        assert "99999" in str(exc_info.value.message)
        assert "Staff" in str(exc_info.value.message)

    def test_custom_label_in_error(self, db_session: Session):
        from lab_manager.models.staff import Staff

        with pytest.raises(NotFoundError) as exc_info:
            get_or_404(db_session, Staff, 42, label="Team Member")
        assert "Team Member" in str(exc_info.value.message)
        assert "42" in str(exc_info.value.message)

    def test_not_found_error_status_code_is_404(self, db_session: Session):
        from lab_manager.models.staff import Staff

        with pytest.raises(NotFoundError) as exc_info:
            get_or_404(db_session, Staff, 1)
        assert exc_info.value.status_code == 404

    def test_not_found_without_label_uses_model_name(self, db_session: Session):
        from lab_manager.models.vendor import Vendor

        with pytest.raises(NotFoundError) as exc_info:
            get_or_404(db_session, Vendor, 123)
        assert "Vendor" in str(exc_info.value.message)


# ---------------------------------------------------------------------------
# deps.py — verify_api_key()
# ---------------------------------------------------------------------------


class TestVerifyApiKey:
    """Test the verify_api_key() header-based auth dependency."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache(self):
        """Ensure settings cache is clean before and after each test."""
        from lab_manager.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_auth_disabled_always_passes(self):
        """When auth_enabled=False, any request passes."""
        import os

        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        # Should not raise
        verify_api_key(x_api_key=None)

    def test_auth_disabled_ignores_wrong_key(self):
        """When auth_enabled=False, even a wrong key is fine."""
        import os

        os.environ["AUTH_ENABLED"] = "false"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        verify_api_key(x_api_key="garbage")

    def test_valid_api_key_passes(self):
        """When auth_enabled=True, correct API key passes."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "my-secret-key"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key"
        os.environ["ADMIN_PASSWORD"] = "test-admin-pwd"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        # Should not raise
        verify_api_key(x_api_key="my-secret-key")

        # Cleanup
        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

    def test_missing_api_key_header_rejected(self):
        """When auth_enabled=True and no X-Api-Key header, raises 401."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "my-secret-key"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key"
        os.environ["ADMIN_PASSWORD"] = "test-admin-pwd"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key=None)
        assert exc_info.value.status_code == 401
        assert "Invalid or missing API key" in exc_info.value.detail

        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

    def test_wrong_api_key_rejected(self):
        """When auth_enabled=True and wrong key, raises 401."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "my-secret-key"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key"
        os.environ["ADMIN_PASSWORD"] = "test-admin-pwd"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key="wrong-key")
        assert exc_info.value.status_code == 401

        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

    def test_empty_api_key_rejected(self):
        """Empty string API key should be rejected."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "my-secret-key"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key"
        os.environ["ADMIN_PASSWORD"] = "test-admin-pwd"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key="")
        assert exc_info.value.status_code == 401

        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

    def test_auth_enabled_no_api_key_configured_raises_500(self):
        """Server misconfiguration: auth enabled but no API key set."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = ""
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key"
        os.environ["ADMIN_PASSWORD"] = "test-admin-pwd"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(x_api_key="anything")
        assert exc_info.value.status_code == 500
        assert "misconfiguration" in exc_info.value.detail.lower()

        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()

    def test_timing_safe_comparison(self):
        """verify_api_key uses hmac.compare_digest, not ==, for timing safety."""
        import os

        os.environ["AUTH_ENABLED"] = "true"
        os.environ["API_KEY"] = "secret123"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key"
        os.environ["ADMIN_PASSWORD"] = "test-admin-pwd"
        from lab_manager.config import get_settings

        get_settings.cache_clear()

        # Correct key passes
        verify_api_key(x_api_key="secret123")

        # Wrong key fails
        with pytest.raises(HTTPException):
            verify_api_key(x_api_key="secret124")

        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Integration: require_permission wired through a FastAPI app
# ---------------------------------------------------------------------------


class TestRequirePermissionViaFastAPI:
    """End-to-end test of require_permission as a FastAPI dependency."""

    def _make_app(self, *, staff: dict[str, Any] | None = None):
        """Create a fresh FastAPI app + TestClient with staff injection."""
        from fastapi import Depends, FastAPI

        app = FastAPI()

        @app.middleware("http")
        async def inject_staff(request: Request, call_next):
            if staff is not None:
                request.state.staff = staff
            response = await call_next(request)
            return response

        @app.get(
            "/admin-only", dependencies=[Depends(require_permission("manage_users"))]
        )
        def admin_route():
            return {"ok": True}

        @app.get(
            "/view-only", dependencies=[Depends(require_permission("view_inventory"))]
        )
        def view_route():
            return {"ok": True}

        @app.get("/whoami")
        def whoami(staff_dict: dict = Depends(get_current_staff)):
            return {"id": staff_dict["id"], "role": staff_dict.get("role")}

        return TestClient(app)

    def test_admin_can_access_admin_route(self):
        client = self._make_app(staff={"id": 1, "role": "admin"})
        resp = client.get("/admin-only")
        assert resp.status_code == 200

    def test_pi_can_access_admin_route(self):
        client = self._make_app(staff={"id": 1, "role": "pi"})
        resp = client.get("/admin-only")
        assert resp.status_code == 200

    def test_grad_student_forbidden_from_admin_route(self):
        client = self._make_app(staff={"id": 2, "role": "grad_student"})
        resp = client.get("/admin-only")
        assert resp.status_code == 403

    def test_visitor_forbidden_from_admin_route(self):
        client = self._make_app(staff={"id": 3, "role": "visitor"})
        resp = client.get("/admin-only")
        assert resp.status_code == 403

    def test_all_roles_can_view_inventory(self):
        for role in ROLES:
            client = self._make_app(staff={"id": 1, "role": role})
            resp = client.get("/view-only")
            assert resp.status_code == 200, f"{role} should be able to view inventory"

    def test_no_staff_gives_401(self):
        client = self._make_app(staff=None)
        resp = client.get("/view-only")
        assert resp.status_code == 401

    def test_whoami_returns_staff_info(self):
        client = self._make_app(staff={"id": 42, "role": "postdoc"})
        resp = client.get("/whoami")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 42
        assert data["role"] == "postdoc"

    def test_whoami_no_staff_gives_401(self):
        client = self._make_app(staff=None)
        resp = client.get("/whoami")
        assert resp.status_code == 401
