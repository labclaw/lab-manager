"""RBAC permission system tests."""

from __future__ import annotations

from lab_manager.models.staff import ROLE_PERMISSIONS, StaffRole


def test_role_enum_values():
    assert StaffRole.admin == "admin"
    assert StaffRole.manager == "manager"
    assert StaffRole.member == "member"
    assert StaffRole.viewer == "viewer"


def test_role_hierarchy():
    """Higher roles include all permissions of lower roles."""
    viewer = ROLE_PERMISSIONS["viewer"]
    member = ROLE_PERMISSIONS["member"]
    manager = ROLE_PERMISSIONS["manager"]
    admin = ROLE_PERMISSIONS["admin"]

    assert viewer < member
    assert member < manager
    assert manager < admin


def test_viewer_read_only():
    perms = ROLE_PERMISSIONS["viewer"]
    assert "read" in perms
    assert "create" not in perms
    assert "delete" not in perms


def test_member_can_create_update():
    perms = ROLE_PERMISSIONS["member"]
    assert "read" in perms
    assert "create" in perms
    assert "update" in perms
    assert "delete" not in perms
    assert "import" not in perms


def test_manager_can_delete_import():
    perms = ROLE_PERMISSIONS["manager"]
    assert "delete" in perms
    assert "review" in perms
    assert "import" in perms
    assert "admin" not in perms


def test_admin_has_all():
    perms = ROLE_PERMISSIONS["admin"]
    assert "admin" in perms
    assert "import" in perms
    assert "delete" in perms


def test_staff_permissions_property(db_session):
    from lab_manager.models.staff import Staff

    staff = Staff(name="Test User", role="manager")
    db_session.add(staff)
    db_session.flush()
    assert "delete" in staff.permissions
    assert "admin" not in staff.permissions
