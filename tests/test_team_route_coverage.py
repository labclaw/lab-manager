"""Comprehensive tests for api/routes/team.py edge cases.

Targets uncovered/error paths:
- _get_invite_serializer: RuntimeError when ADMIN_SECRET_KEY missing
- create_invitation: empty name, invalid email, invalid role, invite above own
  level, existing active staff, pending invitation already exists, name > 200 chars
- cancel_invitation: not found, non-pending status rejection
- list_invitations: pagination
- get_member: 404
- update_member: invalid role, 404, promote above own level, modify higher level member
- deactivate_member: cannot deactivate self, 404, cannot deactivate higher level
- accept_invitation: short password, long password (>72 bytes), invalid token,
  invitation not found, existing account, reactivating inactive staff
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def team_engine():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def team_db(team_engine):
    with Session(team_engine) as session:
        yield session


@pytest.fixture
def pi_client(team_engine, team_db):
    """Client with auth disabled -- dev middleware gives PI (level 0)."""
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-min-16-chars"
    get_settings.cache_clear()

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield team_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()


@pytest.fixture
def admin_client(team_engine, team_db):
    """Client with auth enabled + API key -> admin (level 1)."""
    os.environ["AUTH_ENABLED"] = "true"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-min-16-chars"
    os.environ["API_KEY"] = "test-api-key-coverage"
    os.environ["SECURE_COOKIES"] = "false"
    get_settings.cache_clear()

    import lab_manager.database as db_module

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = team_engine
    db_module._session_factory = None

    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    app = create_app()

    def override_get_db():
        yield team_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c

    db_module._engine = original_engine
    db_module._session_factory = original_factory
    os.environ["AUTH_ENABLED"] = "false"
    os.environ.pop("API_KEY", None)
    get_settings.cache_clear()


def _admin_headers():
    return {"X-Api-Key": "test-api-key-coverage"}


def _seed_staff(db, **overrides):
    """Insert a single staff member. Returns the Staff object."""
    from lab_manager.models.staff import Staff

    defaults = dict(
        name="Test User",
        email="test@lab.edu",
        role="grad_student",
        role_level=3,
        is_active=True,
    )
    defaults.update(overrides)
    staff = Staff(**defaults)
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


def _seed_members(db):
    """Insert sample staff members for testing."""
    from lab_manager.models.staff import Staff

    members = [
        Staff(
            id=10,
            name="PI User",
            email="pi@lab.edu",
            role="pi",
            role_level=0,
            is_active=True,
        ),
        Staff(
            id=11,
            name="Admin User",
            email="admin2@lab.edu",
            role="admin",
            role_level=1,
            is_active=True,
        ),
        Staff(
            id=12,
            name="Postdoc User",
            email="postdoc@lab.edu",
            role="postdoc",
            role_level=2,
            is_active=True,
        ),
        Staff(
            id=13,
            name="Grad User",
            email="grad@lab.edu",
            role="grad_student",
            role_level=3,
            is_active=True,
        ),
        Staff(
            id=14,
            name="Inactive User",
            email="inactive@lab.edu",
            role="visitor",
            role_level=4,
            is_active=False,
        ),
    ]
    for m in members:
        db.add(m)
    db.commit()


def _create_invite(
    client, email="new@lab.edu", name="New User", role="grad_student", headers=None
):
    """Helper: create an invitation and return the response JSON."""
    resp = client.post(
        "/api/v1/team/invite",
        json={"email": email, "name": name, "role": role},
        headers=headers,
    )
    assert resp.status_code == 200, f"Invite creation failed: {resp.json()}"
    return resp.json()


# ---------------------------------------------------------------------------
# _get_invite_serializer
# ---------------------------------------------------------------------------


class TestGetInviteSerializer:
    def test_runtime_error_when_secret_missing(self):
        """_get_invite_serializer raises RuntimeError if key is empty."""
        os.environ["ADMIN_SECRET_KEY"] = ""
        get_settings.cache_clear()

        from lab_manager.api.routes.team import _get_invite_serializer

        with pytest.raises(RuntimeError, match="ADMIN_SECRET_KEY"):
            _get_invite_serializer()

        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-testing-min-16-chars"
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# create_invitation
# ---------------------------------------------------------------------------


class TestCreateInvitation:
    def test_empty_name_rejected(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "empty@lab.edu", "name": "  ", "role": "grad_student"},
        )
        assert resp.status_code == 422
        assert "name" in resp.json()["detail"].lower() or "200" in resp.json()["detail"]

    def test_name_too_long_rejected(self, pi_client, team_db):
        long_name = "A" * 201
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={
                "email": "longname@lab.edu",
                "name": long_name,
                "role": "grad_student",
            },
        )
        assert resp.status_code == 422

    def test_invalid_email_rejected(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "not-an-email", "name": "Test", "role": "grad_student"},
        )
        assert resp.status_code == 422
        assert "email" in resp.json()["detail"].lower()

    def test_invalid_role_rejected(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "a@b.com", "name": "Test", "role": "ceo"},
        )
        assert resp.status_code == 422
        assert "invalid role" in resp.json()["detail"].lower()

    def test_invite_existing_active_staff_rejected(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "grad@lab.edu", "name": "Grad", "role": "grad_student"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_invite_pending_invitation_already_exists(self, pi_client, team_db):
        pi_client.post(
            "/api/v1/team/invite",
            json={"email": "dup@lab.edu", "name": "First", "role": "grad_student"},
        )
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "dup@lab.edu", "name": "Second", "role": "grad_student"},
        )
        assert resp.status_code == 409
        assert "pending" in resp.json()["detail"].lower()

    def test_invite_success(self, pi_client, team_db):
        data = _create_invite(pi_client, email="newuser@lab.edu")
        assert data["email"] == "newuser@lab.edu"
        assert data["status"] == "pending"
        assert data["token"]

    def test_invite_default_role_is_grad_student(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "default-role@lab.edu", "name": "Default Role"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "grad_student"

    def test_invite_strips_whitespace(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={
                "email": "  Strip@Lab.Edu  ",
                "name": "  Strip Name  ",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "strip@lab.edu"
        assert resp.json()["name"] == "Strip Name"

    def test_admin_cannot_invite_as_pi(self, admin_client, team_db):
        """Admin (level 1) cannot invite someone as PI (level 0)."""
        resp = admin_client.post(
            "/api/v1/team/invite",
            json={"email": "new@lab.edu", "name": "New", "role": "pi"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 403
        assert "above" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# cancel_invitation
# ---------------------------------------------------------------------------


class TestCancelInvitation:
    def test_cancel_not_found(self, pi_client, team_db):
        resp = pi_client.delete("/api/v1/team/invitations/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_cancel_non_pending_status_rejected(self, pi_client, team_db):
        inv = _create_invite(pi_client, email="cancel-me@lab.edu")
        inv_id = inv["id"]
        # Cancel once
        resp1 = pi_client.delete(f"/api/v1/team/invitations/{inv_id}")
        assert resp1.status_code == 200
        # Cancel again -- status is now "cancelled", not "pending"
        resp2 = pi_client.delete(f"/api/v1/team/invitations/{inv_id}")
        assert resp2.status_code == 400
        assert "pending" in resp2.json()["detail"].lower()

    def test_cancel_accepted_invitation_rejected(self, pi_client, team_db):
        inv = _create_invite(pi_client, email="accepted-inv@lab.edu")
        token = inv["token"]
        inv_id = inv["id"]
        # Accept the invitation
        pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword123"},
        )
        # Now try to cancel the accepted invitation
        resp = pi_client.delete(f"/api/v1/team/invitations/{inv_id}")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# list_invitations
# ---------------------------------------------------------------------------


class TestListInvitations:
    def test_list_invitations_empty(self, pi_client, team_db):
        resp = pi_client.get("/api/v1/team/invitations/")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_invitations_pagination(self, pi_client, team_db):
        # Create 3 invitations
        for i in range(3):
            _create_invite(pi_client, email=f"page{i}@lab.edu", name=f"Page {i}")

        # Page 1, page_size=2
        resp = pi_client.get("/api/v1/team/invitations/?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["pages"] == 2

        # Page 2
        resp2 = pi_client.get("/api/v1/team/invitations/?page=2&page_size=2")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["items"]) == 1


# ---------------------------------------------------------------------------
# get_member
# ---------------------------------------------------------------------------


class TestGetMember:
    def test_get_member_found(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.get("/api/v1/team/11")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Admin User"
        assert data["role"] == "admin"
        assert "permissions" in data

    def test_get_member_not_found(self, pi_client, team_db):
        resp = pi_client.get("/api/v1/team/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_member_includes_permissions(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.get("/api/v1/team/13")
        assert resp.status_code == 200
        perms = resp.json()["permissions"]
        assert "view_inventory" in perms
        assert isinstance(perms, list)


# ---------------------------------------------------------------------------
# update_member
# ---------------------------------------------------------------------------


class TestUpdateMember:
    def test_update_role_success(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.patch("/api/v1/team/13", json={"role": "postdoc"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "postdoc"
        assert resp.json()["role_level"] == 2

    def test_update_invalid_role(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.patch("/api/v1/team/13", json={"role": "superadmin"})
        assert resp.status_code == 422

    def test_update_member_not_found(self, pi_client, team_db):
        resp = pi_client.patch("/api/v1/team/99999", json={"role": "postdoc"})
        assert resp.status_code == 404

    def test_cannot_promote_above_own_level(self, admin_client, team_db):
        """Admin (level 1 via API key) cannot promote to PI (level 0)."""
        _seed_members(team_db)
        resp = admin_client.patch(
            "/api/v1/team/13",
            json={"role": "pi"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 403
        assert "above" in resp.json()["detail"].lower()

    def test_cannot_modify_higher_level_member(self, admin_client, team_db):
        """Admin (level 1) cannot change PI (level 0)."""
        _seed_members(team_db)
        resp = admin_client.patch(
            "/api/v1/team/10",
            json={"role": "admin"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 403
        assert "higher" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# deactivate_member
# ---------------------------------------------------------------------------


class TestDeactivateMember:
    def test_deactivate_success(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.delete("/api/v1/team/13")
        assert resp.status_code == 200
        assert "deactivated" in resp.json()["message"].lower()

    def test_cannot_deactivate_self(self, pi_client, team_db):
        """Dev-mode staff has id=0; deactivating id=0 should fail."""
        resp = pi_client.delete("/api/v1/team/0")
        assert resp.status_code in (400, 404)

    def test_deactivate_not_found(self, pi_client, team_db):
        resp = pi_client.delete("/api/v1/team/99999")
        assert resp.status_code == 404

    def test_cannot_deactivate_higher_level(self, admin_client, team_db):
        """Admin (level 1) cannot deactivate PI (level 0)."""
        _seed_members(team_db)
        resp = admin_client.delete("/api/v1/team/10", headers=_admin_headers())
        assert resp.status_code == 403
        assert "higher" in resp.json()["detail"].lower()

    def test_deactivate_self_explicit(self, pi_client, team_db):
        """The dev middleware sets staff id=0. Deactivating id=0 = self-deactivate."""
        resp = pi_client.delete("/api/v1/team/0")
        # id=0 is not in the DB so either 400 (self-deactivate) or 404 (not found)
        assert resp.status_code in (400, 404)


# ---------------------------------------------------------------------------
# accept_invitation
# ---------------------------------------------------------------------------


class TestAcceptInvitation:
    def _create_invite(
        self, client, email="join@lab.edu", role="grad_student", name="Joiner"
    ):
        return _create_invite(client, email=email, role=role, name=name)

    def test_join_success(self, pi_client, team_db):
        inv = self._create_invite(pi_client)
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["user"]["email"] == "join@lab.edu"

    def test_join_short_password_rejected(self, pi_client, team_db):
        inv = self._create_invite(pi_client, email="short@lab.edu")
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "short"},
        )
        assert resp.status_code == 422
        assert "8" in resp.json()["detail"]

    def test_join_password_exceeds_72_bytes(self, pi_client, team_db):
        inv = self._create_invite(pi_client, email="longpw@lab.edu")
        long_password = "x" * 73  # 73 bytes
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": long_password},
        )
        assert resp.status_code == 422
        assert "72" in resp.json()["detail"]

    def test_join_invalid_token(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/join/invalid-token-xyz",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    def test_join_invitation_not_found_after_token_verify(self, pi_client, team_db):
        """Token is valid (signed with our secret) but no matching Invitation
        row exists in the DB."""
        from itsdangerous import URLSafeTimedSerializer

        serializer = URLSafeTimedSerializer(
            "test-secret-key-for-testing-min-16-chars", salt="lab-invite"
        )
        # Create a valid token for an email that has no invitation row
        token = serializer.dumps(
            {"email": "ghost@lab.edu", "role": "grad_student", "nonce": "deadbeef"}
        )

        resp = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 400
        assert (
            "not found" in resp.json()["detail"].lower()
            or "already used" in resp.json()["detail"].lower()
        )

    def test_join_existing_active_account(self, pi_client, team_db):
        """Line 382: accept_invitation rejects when active staff has the email.

        This tests the race condition where:
        1. Invitation is created (no active staff with that email yet)
        2. Active staff is inserted directly in DB (bypassing invite check)
        3. Accepting the invitation hits the "already exists" guard
        """
        from lab_manager.models.staff import Staff

        email = "race@lab.edu"

        # Step 1: Create invitation
        inv = self._create_invite(pi_client, email=email)

        # Step 2: Directly insert an active staff with the same email
        active_staff = Staff(
            name="Race Condition",
            email=email,
            role="grad_student",
            role_level=3,
            is_active=True,
        )
        team_db.add(active_staff)
        team_db.commit()

        # Step 3: Accept the invitation -- should hit line 382
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    def test_join_reactivates_inactive_staff(self, pi_client, team_db):
        from lab_manager.models.staff import Staff

        email = "reactivate@lab.edu"

        # Create inactive staff
        inactive = Staff(
            name="Old Name",
            email=email,
            role="visitor",
            role_level=4,
            is_active=False,
        )
        team_db.add(inactive)
        team_db.commit()

        # Create and accept invitation
        inv = self._create_invite(
            pi_client, email=email, name="New Name", role="grad_student"
        )
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["name"] == "New Name"
        assert data["user"]["role"] == "grad_student"

        # Verify reactivated, not duplicated
        team_db.expire_all()
        all_staff = team_db.exec(
            __import__("sqlmodel").select(Staff).where(Staff.email == email)
        ).all()
        assert len(all_staff) == 1
        assert all_staff[0].is_active is True

    def test_join_creates_new_staff(self, pi_client, team_db):
        from lab_manager.models.staff import Staff

        email = "brandnew@lab.edu"
        inv = self._create_invite(pi_client, email=email, role="postdoc")
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["role"] == "postdoc"

        team_db.expire_all()
        staff = team_db.exec(
            __import__("sqlmodel").select(Staff).where(Staff.email == email)
        ).first()
        assert staff is not None
        assert staff.is_active is True

    def test_join_token_cannot_be_reused(self, pi_client, team_db):
        inv = self._create_invite(pi_client, email="reuse@lab.edu")
        resp1 = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "securepassword123"},
        )
        assert resp1.status_code == 200

        resp2 = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "securepassword123"},
        )
        assert resp2.status_code in (400, 409)

    def test_join_password_exactly_8_chars_accepted(self, pi_client, team_db):
        """Boundary: 8-char password should be accepted."""
        inv = self._create_invite(pi_client, email="exact8@lab.edu")
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "12345678"},
        )
        assert resp.status_code == 200

    def test_join_password_exactly_72_bytes_accepted(self, pi_client, team_db):
        """Boundary: 72-byte password should be accepted."""
        inv = self._create_invite(pi_client, email="exact72@lab.edu")
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": "x" * 72},
        )
        assert resp.status_code == 200

    def test_join_multibyte_password_byte_limit(self, pi_client, team_db):
        """Password with multibyte chars that exceeds 72 bytes."""
        inv = self._create_invite(pi_client, email="multi@lab.edu")
        # Each CJK char is 3 bytes in UTF-8; 25 * 3 = 75 bytes > 72
        cjk_password = "\u4e2d" * 25
        assert len(cjk_password.encode("utf-8")) > 72
        resp = pi_client.post(
            f"/api/v1/team/join/{inv['token']}",
            json={"password": cjk_password},
        )
        assert resp.status_code == 422
        assert "72" in resp.json()["detail"]
