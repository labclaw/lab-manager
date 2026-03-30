"""Tests for team management endpoints."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import select
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.api.auth import ROLE_LEVELS
from lab_manager.config import get_settings


# ---------------------------------------------------------------------------
# Fixtures — standard (auth disabled, PI role via dev middleware)
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
    """Client with auth disabled — dev middleware gives PI (level 0)."""
    os.environ["AUTH_ENABLED"] = "false"
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-team-tests"
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
    os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-team-tests"
    os.environ["API_KEY"] = "test-api-key-team"
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
    return {"X-Api-Key": "test-api-key-team"}


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


# ---------------------------------------------------------------------------
# Tests: List members (PI role — has manage_users)
# ---------------------------------------------------------------------------


class TestListMembers:
    def test_list_members_returns_all(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.get("/api/v1/team/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    def test_list_members_filter_active(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.get("/api/v1/team/?is_active=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert all(m["is_active"] for m in data["items"])

    def test_list_members_requires_manage_users(self, team_db):
        """Unauthenticated request to team endpoints returns 401."""
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-team-tests"
        get_settings.cache_clear()

        from lab_manager.api.app import create_app
        from lab_manager.api.deps import get_db

        app = create_app()

        def override_get_db():
            yield team_db

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as c:
            resp = c.get("/api/v1/team/")
            assert resp.status_code == 401

        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Tests: Get member detail
# ---------------------------------------------------------------------------


class TestGetMember:
    def test_get_member_detail(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.get("/api/v1/team/11")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Admin User"
        assert data["role"] == "admin"
        assert "permissions" in data

    def test_get_member_not_found(self, pi_client, team_db):
        resp = pi_client.get("/api/v1/team/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Update role (PI can promote/demote anyone)
# ---------------------------------------------------------------------------


class TestUpdateRole:
    def test_update_role_success(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.patch("/api/v1/team/13", json={"role": "postdoc"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "postdoc"
        assert resp.json()["role_level"] == ROLE_LEVELS["postdoc"]

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

    def test_cannot_modify_higher_role_member(self, admin_client, team_db):
        """Admin (level 1) cannot change PI (level 0)."""
        _seed_members(team_db)
        resp = admin_client.patch(
            "/api/v1/team/10",
            json={"role": "admin"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 403
        assert "higher" in resp.json()["detail"].lower()

    def test_invalid_role_rejected(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.patch("/api/v1/team/13", json={"role": "superadmin"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Deactivate member
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

    def test_cannot_deactivate_higher_role(self, admin_client, team_db):
        """Admin (level 1) cannot deactivate PI (level 0)."""
        _seed_members(team_db)
        resp = admin_client.delete("/api/v1/team/10", headers=_admin_headers())
        assert resp.status_code == 403

    def test_deactivate_not_found(self, pi_client, team_db):
        resp = pi_client.delete("/api/v1/team/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Invite
# ---------------------------------------------------------------------------


class TestInvite:
    def test_create_invitation_success(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={
                "email": "newuser@lab.edu",
                "name": "New User",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@lab.edu"
        assert data["role"] == "grad_student"
        assert data["status"] == "pending"
        assert "token" not in data  # token must not leak in API response

    def test_invite_duplicate_email_rejected(self, pi_client, team_db):
        """Cannot invite the same email twice while pending."""
        pi_client.post(
            "/api/v1/team/invite",
            json={"email": "dup@lab.edu", "name": "First", "role": "grad_student"},
        )
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "dup@lab.edu", "name": "Second", "role": "grad_student"},
        )
        assert resp.status_code == 409

    def test_invite_existing_active_user_rejected(self, pi_client, team_db):
        _seed_members(team_db)
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={
                "email": "grad@lab.edu",
                "name": "Grad",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 409

    def test_admin_cannot_invite_as_pi(self, admin_client, team_db):
        """Admin (level 1) cannot invite someone as PI (level 0)."""
        resp = admin_client.post(
            "/api/v1/team/invite",
            json={"email": "new@lab.edu", "name": "New", "role": "pi"},
            headers=_admin_headers(),
        )
        assert resp.status_code == 403

    def test_invite_invalid_email(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "not-an-email", "name": "Test", "role": "grad_student"},
        )
        assert resp.status_code == 422

    def test_invite_invalid_role(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/invite",
            json={"email": "a@b.com", "name": "Test", "role": "ceo"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Join (accept invitation)
# ---------------------------------------------------------------------------


class TestJoinInvitation:
    def _create_invite(self, client, db, email="join@lab.edu", role="grad_student"):
        """Create an invite and return the token from DB (not exposed in API)."""
        from lab_manager.models.invitation import Invitation

        resp = client.post(
            "/api/v1/team/invite",
            json={"email": email, "name": "Joiner", "role": role},
        )
        assert resp.status_code == 200
        inv_id = resp.json()["id"]
        inv = db.get(Invitation, inv_id)
        return inv.token

    def test_join_success(self, pi_client, team_db):
        token = self._create_invite(pi_client, team_db)
        resp = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["user"]["email"] == "join@lab.edu"
        assert data["user"]["role"] == "grad_student"

    def test_join_invalid_token(self, pi_client, team_db):
        resp = pi_client.post(
            "/api/v1/team/join/invalid-token-xyz",
            json={"password": "securepassword123"},
        )
        assert resp.status_code == 400

    def test_join_short_password_rejected(self, pi_client, team_db):
        token = self._create_invite(pi_client, team_db, email="short@lab.edu")
        resp = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "short"},
        )
        assert resp.status_code == 422

    def test_join_token_cannot_be_reused(self, pi_client, team_db):
        token = self._create_invite(pi_client, team_db, email="reuse@lab.edu")
        # First join succeeds
        resp1 = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword123"},
        )
        assert resp1.status_code == 200
        # Second join with same token fails
        resp2 = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword123"},
        )
        assert resp2.status_code in (400, 409)

    def test_join_concurrent_accept_prevented(self, pi_client, team_db):
        """Regression test for TOCTOU race in accept_invitation.

        Before the fix, two concurrent requests with the same invitation
        token could both pass the status == "pending" check and create
        duplicate staff accounts.  With ``with_for_update()`` the second
        transaction blocks until the first commits (at which point the
        invitation is no longer pending).

        Because SQLite (used in tests) serialises writes by default we
        verify the serialised outcome: only one account is created.
        """
        from lab_manager.models.invitation import Invitation
        from lab_manager.models.staff import Staff

        token = self._create_invite(pi_client, team_db, email="race@lab.edu")

        # First acceptance succeeds
        resp1 = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword123"},
        )
        assert resp1.status_code == 200

        # Second acceptance must fail (token already used)
        resp2 = pi_client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "securepassword456"},
        )
        assert resp2.status_code in (400, 409)

        # Exactly one staff record for this email
        staff_rows = (
            team_db.execute(select(Staff).where(Staff.email == "race@lab.edu"))
            .scalars()
            .all()
        )
        assert len(staff_rows) == 1

        # Invitation is now accepted, not pending
        inv_rows = (
            team_db.execute(select(Invitation).where(Invitation.token == token))
            .scalars()
            .all()
        )
        assert len(inv_rows) == 1
        assert inv_rows[0].status == "accepted"


# ---------------------------------------------------------------------------
# Tests: Invitations management
# ---------------------------------------------------------------------------


class TestInvitationsManagement:
    def test_list_invitations(self, pi_client, team_db):
        pi_client.post(
            "/api/v1/team/invite",
            json={"email": "a@lab.edu", "name": "A", "role": "grad_student"},
        )
        pi_client.post(
            "/api/v1/team/invite",
            json={"email": "b@lab.edu", "name": "B", "role": "postdoc"},
        )
        resp = pi_client.get("/api/v1/team/invitations/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_cancel_invitation(self, pi_client, team_db):
        create_resp = pi_client.post(
            "/api/v1/team/invite",
            json={
                "email": "cancel@lab.edu",
                "name": "Cancel Me",
                "role": "grad_student",
            },
        )
        inv_id = create_resp.json()["id"]
        resp = pi_client.delete(f"/api/v1/team/invitations/{inv_id}")
        assert resp.status_code == 200
        assert "cancelled" in resp.json()["message"].lower()

    def test_cancel_non_pending_invitation_fails(self, pi_client, team_db):
        """Cannot cancel an already-cancelled invitation."""
        create_resp = pi_client.post(
            "/api/v1/team/invite",
            json={
                "email": "double@lab.edu",
                "name": "Double",
                "role": "grad_student",
            },
        )
        inv_id = create_resp.json()["id"]
        pi_client.delete(f"/api/v1/team/invitations/{inv_id}")
        resp = pi_client.delete(f"/api/v1/team/invitations/{inv_id}")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Configurable API key role
# ---------------------------------------------------------------------------


class TestApiKeyRole:
    def test_api_key_role_limits_permissions(self, team_engine, team_db):
        """API key with role=postdoc cannot manage_users (403)."""
        os.environ["AUTH_ENABLED"] = "true"
        os.environ["ADMIN_SECRET_KEY"] = "test-secret-key-for-team-tests"
        os.environ["API_KEY"] = "test-api-key-role"
        os.environ["API_KEY_ROLE"] = "postdoc"
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
            resp = c.get(
                "/api/v1/team/",
                headers={"X-Api-Key": "test-api-key-role"},
            )
            # postdoc does not have manage_users permission
            assert resp.status_code == 403

        db_module._engine = original_engine
        db_module._session_factory = original_factory
        os.environ.pop("API_KEY_ROLE", None)
        os.environ.pop("API_KEY", None)
        os.environ["AUTH_ENABLED"] = "false"
        get_settings.cache_clear()
