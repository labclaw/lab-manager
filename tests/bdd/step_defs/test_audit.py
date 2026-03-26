"""Step definitions for audit log BDD scenarios."""

import pytest
from pytest_bdd import parsers, scenario, then, when

FEATURE = "../features/audit.feature"


# --- Scenarios ---


@scenario(FEATURE, "List audit logs returns paginated results")
def test_list_audit_logs():
    pass


@scenario(FEATURE, "List audit logs with table filter")
def test_list_audit_filtered():
    pass


@scenario(FEATURE, "Get record history for a specific entity")
def test_record_history():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- When steps ---


@when("I list audit logs", target_fixture="audit_response")
def list_audit_logs(api):
    r = api.get("/api/v1/audit")
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I list audit logs filtered by table "{table}"'),
    target_fixture="audit_response",
)
def list_audit_filtered(api, table):
    r = api.get("/api/v1/audit", params={"table": table})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I get audit history for table "{table}" record {rid:d}'),
    target_fixture="audit_response",
)
def get_record_history(api, table, rid):
    r = api.get(f"/api/v1/audit/{table}/{rid}")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then("the audit response should be successful")
def check_audit_success(audit_response):
    assert "items" in audit_response


@then("the audit response should include pagination info")
def check_audit_pagination(audit_response):
    assert "page" in audit_response
    assert "total" in audit_response
    assert "pages" in audit_response
