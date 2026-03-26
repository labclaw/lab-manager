"""Tests for RBAC permission system (Phase A/B)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
import pytest
from fastapi import FastAPI, Request
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
from lab_manager.config import get_settings


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------


class TestRoleDefinitions:
    def test_seven_roles_defined(self):
        assert len(ROLES) == 7

    def test_all_roles_have_levels(self):
        for role in ROLES:
            assert role in ROLE_LEVELS, f"Role {role!r} missing from ROLE_LEVELS"

    def test_all_roles_have_permissions(self):
        for role in ROLES:
            assert role in ROLE_PERMISSIONS, (
                f"Role {role!r} missing from ROLE_PERMISSIONS"
            )

    def test_role_levels_are_ints(self):
        for role, level in ROLE_LEVELS.items():
            assert isinstance(level, int), f"Level for {role!r} is not int"

    def test_pi_is_level_0(self):
        assert ROLE_LEVELS["pi"] == 0

    def test_admin_is_level_1(self):
        assert ROLE_LEVELS["admin"] == 1

    def test_grad_student_and_tech_same_level(self):
        assert ROLE_LEVELS["grad_student"] == ROLE_LEVELS["tech"] == 3

    def test_undergrad_and_visitor_same_level(self):
        assert ROLE_LEVELS["undergrad"] == ROLE_LEVELS["visitor"] == 4


# ---------------------------------------------------------------------------
# Permission sets
# ---------------------------------------------------------------------------


class TestPermissionSets:
    def test_pi_has_all_permissions(self):
        assert ROLE_PERMISSIONS["pi"] == ALL_PERMISSIONS

    def test_admin_has_all_except_delete(self):
        assert ROLE_PERMISSIONS["admin"] == ALL_PERMISSIONS - {"delete_records"}

    def test_delete_records_is_pi_only(self):
        for role in ROLES:
            perms = get_permissions(role)
            if role == "pi":
                assert "delete_records" in perms
            else:
                assert "delete_records" not in perms, (
                    f"Role {role!r} should not have delete_records"
                )

    def test_visitor_only_view_permissions(self):
        visitor_perms = get_permissions("visitor")
        expected = frozenset({"view_inventory", "view_documents", "view_equipment"})
        assert visitor_perms == expected

    def test_undergrad_only_view_permissions(self):
        undergrad_perms = get_permissions("undergrad")
        expected = frozenset({"view_inventory", "view_documents", "view_equipment"})
        assert undergrad_perms == expected

    def test_grad_student_can_ask_ai(self):
        assert "ask_ai" in get_permissions("grad_student")

    def test_grad_student_can_request_order(self):
        assert "request_order" in get_permissions("grad_student")

    def test_grad_student_cannot_create_orders(self):
        assert "create_orders" not in get_permissions("grad_student")

    def test_postdoc_can_create_orders(self):
        assert "create_orders" in get_permissions("postdoc")

    def test_postdoc_cannot_manage_users(self):
        assert "manage_users" not in get_permissions("postdoc")

    def test_tech_can_manage_alerts(self):
        assert "manage_alerts" in get_permissions("tech")

    def test_tech_cannot_create_orders(self):
        assert "create_orders" not in get_permissions("tech")

    def test_admin_can_manage_users(self):
        assert "manage_users" in get_permissions("admin")

    def test_admin_can_approve_orders(self):
        assert "approve_orders" in get_permissions("admin")

    def test_unknown_role_returns_empty(self):
        assert get_permissions("nonexistent") == frozenset()

    def test_all_permission_values_are_frozensets(self):
        for role, perms in ROLE_PERMISSIONS.items():
            assert isinstance(perms, frozenset), (
                f"Permissions for {role!r} is not frozenset"
            )


# ---------------------------------------------------------------------------
# get_permissions caching
# ---------------------------------------------------------------------------


class TestGetPermissions:
    def test_returns_frozenset(self):
        result = get_permissions("pi")
        assert isinstance(result, frozenset)

    def test_caching_returns_same_object(self):
        a = get_permissions("admin")
        b = get_permissions("admin")
        assert a is b

    def test_all_seven_roles(self):
        for role in ROLES:
            perms = get_permissions(role)
            assert len(perms) > 0 or role in ("undergrad", "visitor")


# ---------------------------------------------------------------------------
# get_current_staff
# ---------------------------------------------------------------------------


class TestGetCurrentStaff:
    def _make_request(self, staff_dict=None):
        """Build a minimal Request-like object with state.staff set."""
        app = FastAPI()

        @app.get("/test")
        def _endpoint(request: Request):
            return get_current_staff(request)

        # We test by setting state via middleware
        @app.middleware("http")
        async def _set_staff(request: Request, call_next):
            request.state.staff = staff_dict
            return await call_next(request)

        return TestClient(app)

    def test_raises_401_when_no_staff(self):
        client = self._make_request(None)
        resp = client.get("/test")
        assert resp.status_code == 401

    def test_raises_401_when_empty_dict(self):
        client = self._make_request({})
        resp = client.get("/test")
        assert resp.status_code == 401

    def test_raises_401_when_no_id(self):
        client = self._make_request({"name": "Test"})
        resp = client.get("/test")
        assert resp.status_code == 401

    def test_returns_staff_when_valid(self):
        staff = {"id": 1, "name": "Test", "role": "pi", "role_level": 0}
        client = self._make_request(staff)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == staff


# ---------------------------------------------------------------------------
# require_permission
# ---------------------------------------------------------------------------


class TestRequirePermission:
    def _make_app(self, perms, staff_dict):
        """Build a test app with a route guarded by require_permission."""
        from fastapi import Depends

        app = FastAPI()

        @app.middleware("http")
        async def _set_staff(request: Request, call_next):
            request.state.staff = staff_dict
            return await call_next(request)

        checker = require_permission(*perms)

        @app.get("/protected", dependencies=[Depends(checker)])
        def _protected():
            return {"ok": True}

        return TestClient(app)

    def test_passes_with_correct_permission(self):
        staff = {"id": 1, "name": "PI", "role": "pi", "role_level": 0}
        client = self._make_app(["view_inventory"], staff)
        resp = client.get("/protected")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_passes_with_multiple_permissions(self):
        staff = {"id": 1, "name": "Admin", "role": "admin", "role_level": 1}
        client = self._make_app(["view_inventory", "manage_users"], staff)
        resp = client.get("/protected")
        assert resp.status_code == 200

    def test_raises_403_when_missing_permission(self):
        staff = {"id": 2, "name": "Visitor", "role": "visitor", "role_level": 4}
        client = self._make_app(["manage_users"], staff)
        resp = client.get("/protected")
        assert resp.status_code == 403
        assert "manage_users" in resp.json()["detail"]

    def test_raises_403_for_partial_permissions(self):
        staff = {"id": 3, "name": "Grad", "role": "grad_student", "role_level": 3}
        client = self._make_app(["view_inventory", "manage_users"], staff)
        resp = client.get("/protected")
        assert resp.status_code == 403

    def test_raises_401_when_not_authenticated(self):
        client = self._make_app(["view_inventory"], None)
        resp = client.get("/protected")
        assert resp.status_code == 401

    def test_delete_records_only_pi(self):
        # PI can delete
        pi_staff = {"id": 1, "name": "PI", "role": "pi", "role_level": 0}
        client = self._make_app(["delete_records"], pi_staff)
        assert client.get("/protected").status_code == 200

        # Admin cannot delete
        admin_staff = {"id": 2, "name": "Admin", "role": "admin", "role_level": 1}
        client = self._make_app(["delete_records"], admin_staff)
        assert client.get("/protected").status_code == 403

    def test_unknown_role_raises_403(self):
        staff = {"id": 99, "name": "X", "role": "unknown_role", "role_level": 99}
        client = self._make_app(["view_inventory"], staff)
        resp = client.get("/protected")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Role hierarchy consistency
# ---------------------------------------------------------------------------


class TestRoleHierarchy:
    """Verify that higher-level roles have strictly more permissions."""

    def test_pi_superset_of_admin(self):
        assert get_permissions("admin") < get_permissions("pi")

    def test_admin_superset_of_postdoc(self):
        assert get_permissions("postdoc") < get_permissions("admin")

    def test_postdoc_superset_of_grad_student(self):
        assert get_permissions("grad_student") < get_permissions("postdoc")

    def test_visitor_subset_of_all_roles(self):
        visitor = get_permissions("visitor")
        for role in ROLES:
            if role != "visitor":
                assert visitor <= get_permissions(role), (
                    f"visitor should be subset of {role}"
                )


# ---------------------------------------------------------------------------
# RBAC lockout / login-counter integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def _rbac_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def _rbac_db(_rbac_engine):
    with Session(_rbac_engine) as session:
        yield session


@pytest.fixture
def _rbac_client(_rbac_engine, _rbac_db):
    """TestClient with auth enabled and a shared in-memory DB."""
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-signing"
    os.environ["ADMIN_PASSWORD"] = "test-admin-password-12345"
    os.environ["API_KEY"] = "test-api-key-12345"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = _rbac_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield _rbac_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory
    os.environ["AUTH_ENABLED"] = "false"
    os.environ.pop("ADMIN_SECRET_KEY", None)
    os.environ.pop("ADMIN_PASSWORD", None)
    os.environ.pop("API_KEY", None)
    get_settings.cache_clear()


def test_successful_login_resets_failed_count(_rbac_client, _rbac_db):
    """After a successful login, failed_login_count must be 0 and locked_until cleared."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Counter User",
        email="counter@example.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("goodpass"),
        failed_login_count=3,
        locked_until=None,
    )
    _rbac_db.add(staff)
    _rbac_db.commit()
    _rbac_db.refresh(staff)
    staff_id = staff.id

    # Successful login
    resp = _rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "counter@example.com", "password": "goodpass"},
    )
    assert resp.status_code == 200

    # Verify counter was reset in the database
    _rbac_db.expire_all()
    s = _rbac_db.get(Staff, staff_id)
    assert s.failed_login_count == 0
    assert s.locked_until is None
    assert s.last_login_at is not None


def test_locked_account_rejected_by_session_middleware(_rbac_client, _rbac_db):
    """A staff account locked via locked_until must be rejected by session middleware."""
    from lab_manager.models.staff import Staff

    staff = Staff(
        name="Locked User",
        email="locked@example.com",
        role="admin",
        is_active=True,
        password_hash=_hash_password("goodpass"),
        failed_login_count=0,
        locked_until=None,
    )
    _rbac_db.add(staff)
    _rbac_db.commit()
    _rbac_db.refresh(staff)

    # Login successfully first (get a session cookie)
    resp = _rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "locked@example.com", "password": "goodpass"},
    )
    assert resp.status_code == 200

    # Verify session works before locking
    resp = _rbac_client.get("/api/v1/vendors/")
    assert resp.status_code == 200

    # Lock the account (simulating admin action or brute-force lockout)
    staff.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    _rbac_db.commit()

    # Session middleware must now reject the request
    resp = _rbac_client.get("/api/v1/vendors/")
    assert resp.status_code == 401
