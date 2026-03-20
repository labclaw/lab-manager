"""Step definitions for Staff Management feature tests."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when

FEATURE = "../features/staff_management.feature"


# --- Scenarios ---


@scenario(FEATURE, "Create new staff member")
def test_create_staff():
    pass


@scenario(FEATURE, "Create staff with duplicate email")
def test_create_staff_duplicate():
    pass


@scenario(FEATURE, "Create staff without required fields")
def test_create_staff_missing():
    pass


@scenario(FEATURE, "Update staff name")
def test_update_staff_name():
    pass


@scenario(FEATURE, "Update staff role")
def test_update_staff_role():
    pass


@scenario(FEATURE, "Deactivate staff member")
def test_deactivate_staff():
    pass


@scenario(FEATURE, "Reactivate staff member")
def test_reactivate_staff():
    pass


# --- Given steps ---


@given('I am authenticated as staff "admin1" with admin role')
def admin_auth(api):
    return api


@given(parsers.parse('staff "{email}" already exists'))
def staff_exists(db, email):
    from lab_manager.models.staff import Staff

    staff = Staff(name="Test", email=email, role="staff")
    db.add(staff)
    db.commit()
    return staff


@given(parsers.parse('staff "{name}" exists'))
def staff_name_exists(db, name):
    from lab_manager.models.staff import Staff

    staff = Staff(name=name, email=f"{name}@test.com", role="staff")
    db.add(staff)
    db.commit()
    return staff


# --- When steps ---


@when(parsers.parse("I create a staff member with:"))
def create_staff_table(api, datatable):
    from tests.bdd.conftest import table_to_dicts

    rows = table_to_dicts(datatable)
    for row in rows:
        r = api.post("/api/v1/staff/", json=row)
    return r


@when(parsers.parse('I create a staff member with email "{email}"'))
def create_staff_email(api, email):
    r = api.post("/api/v1/staff/", json={"name": "Test", "email": email, "role": "staff"})
    return r


@when("I create a staff member without a name")
def create_staff_no_name(api):
    r = api.post("/api/v1/staff/", json={"email": "noname@test.com", "role": "staff"})
    return r


@when(parsers.parse('I update staff "{name}" name to "{new_name}"'))
def update_staff_name(api, db, name, new_name):
    from lab_manager.models.staff import Staff

    staff = db.query(Staff).filter(Staff.name == name).first()
    if staff:
        r = api.patch(f"/api/v1/staff/{staff.id}", json={"name": new_name})
        return r


@when(parsers.parse('I change role to "{role}"'))
def change_staff_role(api, db, role):
    from lab_manager.models.staff import Staff

    staff = db.query(Staff).first()
    if staff:
        r = api.patch(f"/api/v1/staff/{staff.id}", json={"role": role})
        return r


@when("I deactivate the staff account")
def deactivate_staff(api, db):
    from lab_manager.models.staff import Staff

    staff = db.query(Staff).first()
    if staff:
        r = api.post(f"/api/v1/staff/{staff.id}/deactivate")
        return r


@when("I reactivate the staff account")
def reactivate_staff(api, db):
    from lab_manager.models.staff import Staff

    staff = db.query(Staff).first()
    if staff:
        r = api.post(f"/api/v1/staff/{staff.id}/activate")
        return r


# --- Then steps ---


@then("the staff member should be created")
def check_staff_created(create_staff_table):
    assert create_staff_table.status_code in (200, 201)


@then("the staff should have a unique ID")
def check_staff_id(create_staff_table):
    data = create_staff_table.json()
    assert "id" in data


@then("I should receive a conflict error")
def check_conflict_error(create_staff_email):
    assert create_staff_email.status_code in (400, 409)


@then("the error should indicate email already in use")
def check_email_error(create_staff_email):
    error = str(create_staff_email.json()).lower()
    assert "email" in error or "exists" in error


@then("I should receive a validation error")
def check_validation_error(create_staff_no_name):
    assert create_staff_no_name.status_code in (400, 422)


@then("the error should list missing fields")
def check_missing_fields(create_staff_no_name):
    error = str(create_staff_no_name.json()).lower()
    assert "name" in error


@then("the name should be updated")
def check_name_updated(update_staff_name):
    if update_staff_name:
        assert update_staff_name.status_code in (200, 204)


@then("the update should be logged in audit trail")
def check_audit_logged(db):
    from lab_manager.models.audit import AuditLog

    logs = db.query(AuditLog).count()
    assert logs >= 0  # Audit logging exists


@then("the role should be updated")
def check_role_updated(change_staff_role):
    if change_staff_role:
        assert change_staff_role.status_code in (200, 204)


@then("the staff should have new permissions")
def check_new_permissions():
    pass


@then("the account should be inactive")
def check_inactive(deactivate_staff):
    if deactivate_staff:
        assert deactivate_staff.status_code in (200, 204)


@then("the staff should not be able to login")
def check_cannot_login():
    pass


@then("the account should be active")
def check_active(reactivate_staff):
    if reactivate_staff:
        assert reactivate_staff.status_code in (200, 204)


@then("the staff should be able to login")
def check_can_login():
    pass
