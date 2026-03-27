"""E2E tests for team management and RBAC permission enforcement.

Covers: invite team members -> accept invitations -> verify permissions ->
update roles -> deactivate members -> audit trail for team changes.

Each test is self-contained - no inter-test state dependencies.
"""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient


def _suffix() -> str:
    return uuid4().hex[:8]


def _invite_and_accept(
    client: TestClient | httpx.Client,
    role: str = "grad_student",
    prefix: str = "user",
) -> dict:
    """Helper: invite + accept a team member, return invite/user data."""
    suffix = _suffix()
    email = f"{prefix}-{suffix}@test.local"
    invite_resp = client.post(
        "/api/v1/team/invite",
        json={
            "email": email,
            "name": f"{prefix} {suffix}",
            "role": role,
        },
    )
    assert invite_resp.status_code == 200, f"Invite failed: {invite_resp.text}"
    invite_data = invite_resp.json()
    token = invite_data["token"]

    accept_resp = client.post(
        f"/api/v1/team/join/{token}",
        json={"password": "secure-password-12345"},
    )
    assert accept_resp.status_code == 200, f"Accept failed: {accept_resp.text}"
    user_data = accept_resp.json()

    return {
        "email": email,
        "invite_id": invite_data["id"],
        "token": token,
        "user_id": user_data["user"]["id"],
        "role": role,
    }


# ---------------------------------------------------------------------------
# Team Member Invitation Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestTeamInvitationE2E:
    """Full invitation lifecycle: invite -> list -> accept -> verify."""

    def test_01_invite_grad_student(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PI invites a grad student via POST /api/v1/team/invite."""
        client = authenticated_client
        suffix = _suffix()
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"grad-{suffix}@test.local",
                "name": f"Grad Student {suffix}",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 200, f"Invite failed: {resp.text}"
        data = resp.json()
        assert data["email"] == f"grad-{suffix}@test.local"
        assert data["role"] == "grad_student"
        assert data["status"] == "pending"
        assert "token" in data
        assert "id" in data

    def test_02_invite_postdoc(self, authenticated_client: TestClient | httpx.Client):
        """PI invites a postdoc via POST /api/v1/team/invite."""
        client = authenticated_client
        suffix = _suffix()
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"postdoc-{suffix}@test.local",
                "name": f"Postdoc Researcher {suffix}",
                "role": "postdoc",
            },
        )
        assert resp.status_code == 200, f"Invite failed: {resp.text}"
        data = resp.json()
        assert data["role"] == "postdoc"

    def test_03_invite_duplicate_email_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Inviting the same email again returns 409 Conflict."""
        client = authenticated_client
        suffix = _suffix()
        # First invite
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"dup-{suffix}@test.local",
                "name": "First",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 200, f"First invite failed: {resp.text}"
        # Duplicate
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"dup-{suffix}@test.local",
                "name": "Duplicate",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 409, f"Expected 409: {resp.text}"

    def test_04_invite_invalid_role_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Inviting with an invalid role returns 422."""
        client = authenticated_client
        suffix = _suffix()
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"bad-role-{suffix}@test.local",
                "name": "Bad Role",
                "role": "super_admin",
            },
        )
        assert resp.status_code == 422, f"Expected 422: {resp.text}"

    def test_05_invite_invalid_email_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Inviting with an invalid email returns 422."""
        client = authenticated_client
        resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": "not-an-email",
                "name": "Bad Email",
                "role": "grad_student",
            },
        )
        assert resp.status_code == 422, f"Expected 422: {resp.text}"

    def test_06_list_invitations_shows_pending(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/team/invitations/ lists pending invitations."""
        client = authenticated_client
        # Create a fresh invite to guarantee at least 1 pending
        suffix = _suffix()
        email = f"list-{suffix}@test.local"
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={"email": email, "name": f"List Test {suffix}", "role": "tech"},
        )
        assert invite_resp.status_code == 200

        resp = client.get("/api/v1/team/invitations/")
        assert resp.status_code == 200, f"List invitations failed: {resp.text}"
        data = resp.json()
        assert data["total"] >= 1
        emails = [inv["email"] for inv in data["items"]]
        assert email in emails

    def test_07_accept_grad_invitation(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Accept the grad student invitation via POST /api/v1/team/join/{token}."""
        client = authenticated_client
        suffix = _suffix()
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"accept-grad-{suffix}@test.local",
                "name": f"Accept Grad {suffix}",
                "role": "grad_student",
            },
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()["token"]

        resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "secure-password-12345"},
        )
        assert resp.status_code == 200, f"Accept invite failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["user"]["role"] == "grad_student"

    def test_08_accept_postdoc_invitation(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Accept the postdoc invitation."""
        client = authenticated_client
        suffix = _suffix()
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"accept-postdoc-{suffix}@test.local",
                "name": f"Accept Postdoc {suffix}",
                "role": "postdoc",
            },
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()["token"]

        resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "secure-password-12345"},
        )
        assert resp.status_code == 200, f"Accept postdoc invite failed: {resp.text}"
        data = resp.json()
        assert data["user"]["role"] == "postdoc"

    def test_09_accept_used_token_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Re-using an accepted token returns 400."""
        client = authenticated_client
        suffix = _suffix()
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"reuse-{suffix}@test.local",
                "name": f"Reuse Test {suffix}",
                "role": "tech",
            },
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()["token"]

        # First use - should succeed
        resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "secure-password-12345"},
        )
        assert resp.status_code == 200

        # Second use - should fail
        resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "another-password-67890"},
        )
        assert resp.status_code == 400, f"Expected 400: {resp.text}"

    def test_10_accept_short_password_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Accept with password < 8 chars returns 422."""
        client = authenticated_client
        suffix = _suffix()
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"shortpw-{suffix}@test.local",
                "name": f"Short PW {suffix}",
                "role": "tech",
            },
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()["token"]

        resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "short"},
        )
        assert resp.status_code == 422, f"Expected 422: {resp.text}"


# ---------------------------------------------------------------------------
# Team Member Management
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestTeamMemberManagementE2E:
    """List members, view member detail, update roles, deactivate."""

    def test_01_list_members_includes_new_staff(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/team/ lists all team members including invited ones."""
        client = authenticated_client
        # Create and accept a member to guarantee count
        _invite_and_accept(client, role="grad_student", prefix="list-member")
        resp = client.get("/api/v1/team/")
        assert resp.status_code == 200, f"List members failed: {resp.text}"
        data = resp.json()
        # Admin (from setup) + new member >= 2
        assert data["total"] >= 2

    def test_02_list_members_filter_active(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/team/?is_active=true returns only active members."""
        client = authenticated_client
        resp = client.get("/api/v1/team/", params={"is_active": True})
        assert resp.status_code == 200
        data = resp.json()
        for member in data["items"]:
            assert member["is_active"] is True

    def test_03_get_member_detail(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/team/{member_id} returns member with permissions."""
        client = authenticated_client
        result = _invite_and_accept(client, role="tech", prefix="detail")
        staff_id = result["user_id"]

        resp = client.get(f"/api/v1/team/{staff_id}")
        assert resp.status_code == 200, f"Get member failed: {resp.text}"
        data = resp.json()
        assert data["role"] == "tech"
        assert isinstance(data.get("permissions", []), list)

    def test_04_update_member_role(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH /api/v1/team/{member_id} changes role."""
        client = authenticated_client
        result = _invite_and_accept(client, role="tech", prefix="role-update")
        staff_id = result["user_id"]

        resp = client.patch(
            f"/api/v1/team/{staff_id}",
            json={"role": "grad_student"},
        )
        assert resp.status_code == 200, f"Update role failed: {resp.text}"
        data = resp.json()
        assert data["role"] == "grad_student"

        # Verify via GET
        get_resp = client.get(f"/api/v1/team/{staff_id}")
        assert get_resp.json()["role"] == "grad_student"

    def test_05_update_member_invalid_role_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PATCH with invalid role returns 422."""
        client = authenticated_client
        result = _invite_and_accept(client, role="tech", prefix="bad-role")
        staff_id = result["user_id"]

        resp = client.patch(
            f"/api/v1/team/{staff_id}",
            json={"role": "nonexistent_role"},
        )
        assert resp.status_code == 422, f"Expected 422: {resp.text}"

    def test_06_get_nonexistent_member_404(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """GET /api/v1/team/99999 returns 404."""
        client = authenticated_client
        resp = client.get("/api/v1/team/99999")
        assert resp.status_code == 404

    def test_07_deactivate_member(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/team/{member_id} soft-deletes member."""
        client = authenticated_client
        result = _invite_and_accept(client, role="tech", prefix="deactivate")
        staff_id = result["user_id"]

        resp = client.delete(f"/api/v1/team/{staff_id}")
        assert resp.status_code == 200, f"Deactivate failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "ok"

        # Verify member is now inactive
        get_resp = client.get(f"/api/v1/team/{staff_id}")
        assert get_resp.json()["is_active"] is False

    def test_08_deactivate_nonexistent_member_404(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/team/99999 returns 404."""
        client = authenticated_client
        resp = client.delete("/api/v1/team/99999")
        assert resp.status_code == 404

    def test_09_deactivate_self_rejected(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/team/{own_id} returns 400."""
        client = authenticated_client
        # Get our own member info
        me_resp = client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        # Find our staff ID from the team list
        list_resp = client.get("/api/v1/team/")
        members = list_resp.json()["items"]
        my_member = None
        for m in members:
            if m.get("email") == me_data["user"]["email"]:
                my_member = m
                break
        if my_member:
            resp = client.delete(f"/api/v1/team/{my_member['id']}")
            assert resp.status_code == 400, (
                f"Expected 400 (self-deactivate): {resp.text}"
            )


# ---------------------------------------------------------------------------
# Invitation Cancellation
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestInvitationCancelE2E:
    """Cancel pending invitations and verify they cannot be accepted."""

    def test_01_cancel_pending_invitation(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/team/invitations/{id} cancels a pending invite."""
        client = authenticated_client
        suffix = _suffix()
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": f"cancel-{suffix}@test.local",
                "name": f"Cancel Test {suffix}",
                "role": "tech",
            },
        )
        assert invite_resp.status_code == 200
        invite_id = invite_resp.json()["id"]
        token = invite_resp.json()["token"]

        # Cancel it
        cancel_resp = client.delete(f"/api/v1/team/invitations/{invite_id}")
        assert cancel_resp.status_code == 200, f"Cancel failed: {cancel_resp.text}"
        assert cancel_resp.json()["status"] == "ok"

        # Verify the token can no longer be accepted
        accept_resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "cancel-password-12345"},
        )
        assert accept_resp.status_code == 400, (
            f"Expected 400 for cancelled invite: {accept_resp.text}"
        )

    def test_02_cancel_nonexistent_invitation_404(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """DELETE /api/v1/team/invitations/99999 returns 404."""
        client = authenticated_client
        resp = client.delete("/api/v1/team/invitations/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Role Permission Verification
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestRolePermissionE2E:
    """Verify that different roles have the expected permission sets."""

    def test_01_pi_has_all_permissions(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """PI role has the full permission set."""
        client = authenticated_client
        me_resp = client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        user = me_resp.json()["user"]
        assert user["role"] == "pi"

    def test_02_grad_student_cannot_manage_vendors(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Grad student lacks manage_vendors permission."""
        client = authenticated_client
        suffix = _suffix()
        grad_email = f"perms-grad-{suffix}@test.local"
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": grad_email,
                "name": f"Perms Grad {suffix}",
                "role": "grad_student",
            },
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()["token"]

        accept_resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "grad-password-12345"},
        )
        assert accept_resp.status_code == 200

        # Log in as grad student
        client.post("/api/v1/auth/logout")
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": grad_email, "password": "grad-password-12345"},
        )
        assert login_resp.status_code == 200, f"Login as grad failed: {login_resp.text}"

        # Grad student should not be able to create vendors (manage_vendors)
        vendor_resp = client.post(
            "/api/v1/vendors/",
            json={"name": f"Should Fail {suffix}"},
        )
        # Should get 403 Forbidden
        assert vendor_resp.status_code == 403, (
            f"Expected 403 (no manage_vendors): {vendor_resp.status_code} {vendor_resp.text}"
        )

        # But grad student CAN view inventory (view_inventory)
        inv_resp = client.get("/api/v1/inventory/")
        assert inv_resp.status_code == 200

        # Log back in as admin
        client.post("/api/v1/auth/logout")
        admin_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "e2e-admin@test.local",
                "password": "e2e-test-password-secure-12345",
            },
        )
        assert admin_login.status_code == 200

    def test_03_undergrad_has_minimal_permissions(
        self, authenticated_client: TestClient | httpx.Client
    ):
        """Undergrad role can only view inventory, documents, equipment."""
        client = authenticated_client
        suffix = _suffix()
        undergrad_email = f"undergrad-{suffix}@test.local"
        invite_resp = client.post(
            "/api/v1/team/invite",
            json={
                "email": undergrad_email,
                "name": f"Undergrad {suffix}",
                "role": "undergrad",
            },
        )
        assert invite_resp.status_code == 200
        token = invite_resp.json()["token"]

        accept_resp = client.post(
            f"/api/v1/team/join/{token}",
            json={"password": "undergrad-password-12345"},
        )
        assert accept_resp.status_code == 200

        # Log in as undergrad
        client.post("/api/v1/auth/logout")
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": undergrad_email, "password": "undergrad-password-12345"},
        )
        assert login_resp.status_code == 200

        # Undergrad cannot create orders
        order_resp = client.post(
            "/api/v1/orders/",
            json={"po_number": "SHOULD-FAIL", "vendor_id": 1},
        )
        assert order_resp.status_code == 403

        # Undergrad cannot export data
        export_resp = client.get("/api/v1/export/inventory")
        assert export_resp.status_code == 403

        # Undergrad cannot view analytics
        analytics_resp = client.get("/api/v1/analytics/dashboard")
        assert analytics_resp.status_code == 403

        # Undergrad CAN view inventory
        inv_resp = client.get("/api/v1/inventory/")
        assert inv_resp.status_code == 200

        # Log back in as admin
        client.post("/api/v1/auth/logout")
        admin_login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "e2e-admin@test.local",
                "password": "e2e-test-password-secure-12345",
            },
        )
        assert admin_login.status_code == 200
