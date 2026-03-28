"""BDD step definitions for safety_alerts.feature."""

from __future__ import annotations

import pytest
from pytest_bdd import given, when, then, parsers, scenarios

from lab_manager.models.product import Product
from lab_manager.models.inventory import InventoryItem

scenarios("../features/safety_alerts.feature")


# Shared context: store state per-scenario via pytest stash
@pytest.fixture
def safety_ctx():
    return {}


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given('a product with hazard info "H225 Highly flammable liquid"')
def product_flammable(db, safety_ctx):
    p = Product(
        catalog_number="FLAM-001",
        name="Flammable Test Chemical",
        hazard_info="H225 Highly flammable liquid",
        is_hazardous=True,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given('a product with hazard info "H314 Causes severe skin burns"')
def product_corrosive(db, safety_ctx):
    p = Product(
        catalog_number="CORR-001",
        name="Corrosive Test Chemical",
        hazard_info="H314 Causes severe skin burns",
        is_hazardous=True,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given('a product with hazard info "H225 H314 H331"')
def product_multi_hazard(db, safety_ctx):
    p = Product(
        catalog_number="MULTI-001",
        name="Multi-Hazard Chemical",
        hazard_info="H225 H314 H331",
        is_hazardous=True,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given(parsers.parse('a hazardous product "{name}" with hazard info "{hazard_info}"'))
def hazardous_product_with_info(db, safety_ctx, name, hazard_info):
    p = Product(
        catalog_number=f"SAFE-{name[:4].upper()}",
        name=name,
        hazard_info=hazard_info,
        is_hazardous=True,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given(parsers.parse('a non-hazardous product "{name}"'))
def non_hazardous_product(db, safety_ctx, name):
    p = Product(
        catalog_number=f"NON-{name[:4].upper()}",
        name=name,
        is_hazardous=False,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given(parsers.parse('a hazardous product "{name}" with no hazard info'))
def hazardous_product_no_info(db, safety_ctx, name):
    p = Product(
        catalog_number=f"NOH-{name[:4].upper()}",
        name=name,
        is_hazardous=True,
        hazard_info=None,
        cas_number="7664-93-9",
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given(
    parsers.parse(
        'a hazardous product "{name}" with hazard info "{hazard_info}" but no CAS number'
    )
)
def hazardous_product_no_cas(db, safety_ctx, name, hazard_info):
    p = Product(
        catalog_number=f"NOC-{name[:4].upper()}",
        name=name,
        is_hazardous=True,
        hazard_info=hazard_info,
        cas_number=None,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    safety_ctx["product_id"] = p.id
    safety_ctx["product"] = p


@given(parsers.parse("an inventory item for that product with quantity {qty:d}"))
def inventory_item_for_product(db, safety_ctx, qty):
    product = safety_ctx["product"]
    item = InventoryItem(
        product_id=product.id,
        quantity_on_hand=qty,
        status="available",
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    safety_ctx["inventory_id"] = item.id


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when("I request PPE requirements for that product")
def request_ppe_for_product(api, safety_ctx):
    product_id = safety_ctx["product_id"]
    response = api.get(f"/api/v1/safety/ppe/{product_id}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    safety_ctx["ppe_response"] = response.json()


@when(parsers.parse('I request PPE requirements for hazard code "{hazard_code}"'))
def request_ppe_by_code(safety_ctx, hazard_code):
    from lab_manager.services.safety import get_ppe_requirements

    safety_ctx["ppe_result"] = get_ppe_requirements(hazard_code)


@when(parsers.parse("I consume {qty:d} units of that item"))
def consume_units(api, safety_ctx, qty):
    inventory_id = safety_ctx["inventory_id"]
    response = api.post(
        f"/api/v1/inventory/{inventory_id}/consume",
        json={
            "quantity": qty,
            "consumed_by": "test-user",
            "purpose": "testing",
        },
    )
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    safety_ctx["consume_response"] = response.json()


@when("I run the inventory safety scan")
def run_safety_scan(api, safety_ctx):
    response = api.get("/api/v1/safety/inventory-scan")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    safety_ctx["scan_result"] = response.json()


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse('the response should contain "{expected}"'))
def response_contains(safety_ctx, expected):
    # Check PPE API response
    ppe_resp = safety_ctx.get("ppe_response")
    if ppe_resp:
        all_ppe = " ".join(ppe_resp.get("ppe_requirements", []))
        assert expected in all_ppe, f"Expected '{expected}' in '{all_ppe}'"
        return

    # Check direct PPE result
    ppe_result = safety_ctx.get("ppe_result")
    if ppe_result:
        all_ppe = " ".join(ppe_result)
        assert expected in all_ppe, f"Expected '{expected}' in '{all_ppe}'"
        return

    # Check consume response safety reminder
    consume_resp = safety_ctx.get("consume_response")
    if consume_resp and "safety_reminder" in consume_resp:
        all_ppe = " ".join(consume_resp["safety_reminder"].get("ppe_requirements", []))
        assert expected in all_ppe, f"Expected '{expected}' in '{all_ppe}'"
        return

    pytest.fail("No PPE response or result found in context")


@then("the response should contain PPE items from multiple hazard categories")
def response_multiple_categories(safety_ctx):
    ppe_resp = safety_ctx.get("ppe_response")
    assert ppe_resp is not None
    ppe = ppe_resp.get("ppe_requirements", [])
    assert len(ppe) >= 3, f"Expected >=3 PPE items, got {len(ppe)}: {ppe}"


@then(parsers.parse("the response hazard codes should be {codes}"))
def response_hazard_codes(safety_ctx, codes):
    expected = [c.strip().strip('"') for c in codes.split(",")]
    ppe_resp = safety_ctx.get("ppe_response")
    assert ppe_resp is not None
    actual = ppe_resp.get("hazard_codes", [])
    assert actual == expected, f"Expected {expected}, got {actual}"


@then("the response should include a safety reminder")
def response_has_safety_reminder(safety_ctx):
    resp = safety_ctx.get("consume_response")
    assert resp is not None, "No consume response"
    assert "safety_reminder" in resp, f"Expected safety_reminder in response: {resp}"


@then("the safety reminder should contain PPE requirements")
def safety_reminder_has_ppe(safety_ctx):
    resp = safety_ctx.get("consume_response")
    assert resp is not None
    reminder = resp.get("safety_reminder", {})
    ppe = reminder.get("ppe_requirements", [])
    assert len(ppe) > 0, f"Expected PPE requirements in safety reminder: {reminder}"


@then("the response should not include a safety reminder")
def response_no_safety_reminder(safety_ctx):
    resp = safety_ctx.get("consume_response")
    assert resp is not None, "No consume response"
    assert "safety_reminder" not in resp, (
        f"Did not expect safety_reminder in response: {resp}"
    )


@then("the scan should return a warning about missing hazard info")
def scan_missing_hazard_info(safety_ctx):
    result = safety_ctx.get("scan_result")
    assert result is not None, "No scan result"
    warnings = result.get("warnings", [])
    found = any(w["warning_type"] == "missing_hazard_info" for w in warnings)
    assert found, f"Expected missing_hazard_info warning, got: {warnings}"


@then(parsers.parse('the warning should reference "{name}"'))
def scan_warning_references_name(safety_ctx, name):
    result = safety_ctx.get("scan_result")
    assert result is not None, "No scan result"
    warnings = result.get("warnings", [])
    found = any(name in w.get("message", "") for w in warnings)
    assert found, f"Expected warning referencing '{name}', got: {warnings}"


@then("the scan should return a warning about missing CAS number")
def scan_missing_cas(safety_ctx):
    result = safety_ctx.get("scan_result")
    assert result is not None, "No scan result"
    warnings = result.get("warnings", [])
    found = any(w["warning_type"] == "missing_cas_number" for w in warnings)
    assert found, f"Expected missing_cas_number warning, got: {warnings}"


@then("the response should suggest consulting SDS")
def response_suggests_sds(safety_ctx):
    ppe_result = safety_ctx.get("ppe_result")
    assert ppe_result is not None
    all_ppe = " ".join(ppe_result)
    assert "SDS" in all_ppe or "Consult" in all_ppe, (
        f"Expected SDS suggestion, got: {ppe_result}"
    )
