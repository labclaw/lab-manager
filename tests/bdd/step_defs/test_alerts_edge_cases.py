"""Step definitions for alert edge case BDD scenarios."""

import itertools

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from lab_manager.models.alert import Alert

FEATURE = "../features/alerts_edge_cases.feature"

_seq = itertools.count(1)


# --- Scenarios ---


@scenario(FEATURE, "Acknowledge non-existent alert returns 404")
def test_ack_nonexistent():
    pass


@scenario(FEATURE, "Resolve non-existent alert returns 404")
def test_resolve_nonexistent():
    pass


@scenario(FEATURE, "Filter alerts by type")
def test_filter_by_type():
    pass


@scenario(FEATURE, "Filter alerts by severity")
def test_filter_by_severity():
    pass


@scenario(FEATURE, "Resolving an unacknowledged alert also acknowledges it")
def test_resolve_auto_acks():
    pass


@scenario(FEATURE, "Alert summary on empty database")
def test_summary_empty():
    pass


@scenario(FEATURE, "Alert check on empty database")
def test_check_empty():
    pass


# --- Shared state ---


@pytest.fixture
def ctx():
    return {}


# --- Helpers ---


def _create_alert(db, alert_type="expiring_soon", severity="warning"):
    seq = next(_seq)
    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        message=f"Edge test alert {seq}",
        entity_type="inventory",
        entity_id=10000 + seq,
        is_resolved=False,
    )
    db.add(alert)
    db.flush()
    return alert


# --- Given steps ---


@given('alerts of type "expiring_soon" and "low_stock" exist')
def create_typed_alerts(db):
    _create_alert(db, alert_type="expiring_soon")
    _create_alert(db, alert_type="expiring_soon")
    _create_alert(db, alert_type="low_stock")


@given('alerts with severity "warning" and "critical" exist')
def create_severity_alerts(db):
    _create_alert(db, severity="warning")
    _create_alert(db, severity="warning")
    _create_alert(db, severity="critical")


@given("an unacknowledged alert exists", target_fixture="unack_alert")
def create_unack_alert(db):
    alert = _create_alert(db)
    assert alert.is_acknowledged is not True
    return alert


# --- When steps ---


@when(
    parsers.parse("I try to acknowledge alert with id {aid:d}"),
    target_fixture="alert_resp",
)
def ack_nonexistent(api, aid):
    return api.post(f"/api/v1/alerts/{aid}/acknowledge")


@when(
    parsers.parse("I try to resolve alert with id {aid:d}"),
    target_fixture="alert_resp",
)
def resolve_nonexistent(api, aid):
    return api.post(f"/api/v1/alerts/{aid}/resolve")


@when(
    parsers.parse('I list alerts with type "{alert_type}"'),
    target_fixture="alert_list",
)
def list_alerts_by_type(api, alert_type):
    r = api.get("/api/v1/alerts", params={"alert_type": alert_type})
    assert r.status_code == 200, r.text
    return r.json()


@when(
    parsers.parse('I list alerts with severity "{severity}"'),
    target_fixture="alert_list",
)
def list_alerts_by_severity(api, severity):
    r = api.get("/api/v1/alerts", params={"severity": severity})
    assert r.status_code == 200, r.text
    return r.json()


@when("I resolve the unacknowledged alert", target_fixture="alert_resp")
def resolve_unack(api, unack_alert):
    r = api.post(f"/api/v1/alerts/{unack_alert.id}/resolve")
    assert r.status_code == 200, r.text
    return r


@when("I request alert summary", target_fixture="summary_resp")
def request_summary(api):
    r = api.get("/api/v1/alerts/summary")
    assert r.status_code == 200, r.text
    return r.json()


@when("I run alert check", target_fixture="check_resp")
def run_check(api):
    r = api.post("/api/v1/alerts/check")
    assert r.status_code == 200, r.text
    return r.json()


# --- Then steps ---


@then(parsers.parse("the alert response status should be {code:d}"))
def check_alert_status(alert_resp, code):
    assert alert_resp.status_code == code


@then(parsers.parse('all listed alerts should have type "{alert_type}"'))
def check_all_type(alert_list, alert_type):
    for alert in alert_list["items"]:
        assert alert["alert_type"] == alert_type


@then(parsers.parse('all listed alerts should have severity "{severity}"'))
def check_all_severity(alert_list, severity):
    for alert in alert_list["items"]:
        assert alert["severity"] == severity


@then("the alert should be both acknowledged and resolved")
def check_ack_and_resolved(alert_resp):
    data = alert_resp.json()
    assert data["is_acknowledged"] is True
    assert data["is_resolved"] is True


@then(parsers.parse("the summary total should be {n:d}"))
def check_summary_total(summary_resp, n):
    assert summary_resp["total"] == n


@then(parsers.parse("the check should return {n:d} new alerts"))
def check_new_alerts(check_resp, n):
    assert check_resp["new_alerts"] == n
