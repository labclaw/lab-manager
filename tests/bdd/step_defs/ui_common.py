"""Shared UI step definitions for all UI BDD scenarios.

Provides reusable Given/When/Then steps for:
  - Navigation (hash routing)
  - Auth (login/logout)
  - UI assertions (visibility, text, toasts)
  - Data setup via live server (vendor, product, order, inventory, document)

Data setup steps POST to the live server URL via ``live_client`` (httpx) so
that the data is committed in the live server's DB and visible to Playwright.
"""

from pytest_bdd import given, parsers, then, when


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


@given("I am logged in as a scientist")
def logged_in(logged_in_page):
    """Ensures page is authenticated and on the app."""
    return logged_in_page


@given(parsers.parse("I am on the {view_name} view"))
def on_view(logged_in_page, live_server, view_name):
    view_map = {
        "dashboard": "dashboard",
        "documents": "documents",
        "review": "review",
        "inventory": "inventory",
        "orders": "orders",
        "search": "search",
    }
    route = view_map.get(view_name, view_name)
    logged_in_page.goto(f"{live_server}/#/{route}")
    logged_in_page.wait_for_timeout(300)
    return logged_in_page


@when(parsers.parse('I navigate to "{route}"'))
def navigate_to(logged_in_page, live_server, route):
    if route.startswith("#"):
        logged_in_page.goto(f"{live_server}/{route}")
    else:
        logged_in_page.goto(f"{live_server}/#/{route}")
    logged_in_page.wait_for_timeout(300)


@when("I open the app without a hash")
def open_without_hash(logged_in_page, live_server):
    logged_in_page.goto(live_server)
    logged_in_page.wait_for_timeout(300)


@when(parsers.parse('I click the "{button}" nav button'))
def click_nav_button(logged_in_page, button):
    nav = logged_in_page.locator(".nav-links button", has_text=button)
    nav.click()
    logged_in_page.wait_for_timeout(300)


@when("I press the browser back button")
def press_back(logged_in_page):
    logged_in_page.go_back()
    logged_in_page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# URL / view assertions
# ---------------------------------------------------------------------------


@then(parsers.parse('the URL hash should be "{expected_hash}"'))
def check_url_hash(logged_in_page, expected_hash):
    url = logged_in_page.url
    actual_hash = url.split("#", 1)[1] if "#" in url else ""
    expected = expected_hash.lstrip("#")
    assert actual_hash == expected, f"Expected hash '#{expected}', got '#{actual_hash}'"


@then(parsers.parse("the {view_name} view should be visible"))
def view_visible(logged_in_page, view_name):
    view_id = f"view-{view_name}"
    el = logged_in_page.locator(f"#{view_id}")
    assert el.is_visible(), f"View #{view_id} is not visible"


@then(parsers.parse("the {button} nav button should be active"))
def nav_button_active(logged_in_page, button):
    nav = logged_in_page.locator(".nav-links button.active")
    assert button.lower() in nav.text_content().lower()


# ---------------------------------------------------------------------------
# Toast assertions
# ---------------------------------------------------------------------------


@then(parsers.parse('I should see a success toast "{msg}"'))
def check_success_toast(logged_in_page, msg):
    toast = logged_in_page.locator(".toast-success")
    toast.wait_for(state="visible", timeout=3000)
    assert msg.lower() in toast.text_content().lower()


@then(parsers.parse('I should see an error toast containing "{msg}"'))
def check_error_toast(logged_in_page, msg):
    toast = logged_in_page.locator(".toast-error")
    toast.wait_for(state="visible", timeout=3000)
    assert msg.lower() in toast.text_content().lower()


@then(parsers.parse('I should see an error toast "{msg}"'))
def check_error_toast_exact(logged_in_page, msg):
    toast = logged_in_page.locator(".toast-error")
    toast.wait_for(state="visible", timeout=3000)
    assert msg.lower() in toast.text_content().lower()


# ---------------------------------------------------------------------------
# Table / list assertions
# ---------------------------------------------------------------------------


@then(parsers.parse("I should see a table with columns {columns}"))
def check_table_columns(logged_in_page, columns):
    # columns is a comma-separated string like '"Product", "Location", "Qty"'
    col_names = [c.strip().strip('"').strip("'") for c in columns.split(",")]
    header = logged_in_page.locator(".doc-header, .table-header, thead")
    text = header.text_content()
    for col in col_names:
        assert col.lower() in text.lower(), f"Column '{col}' not found in header"


@then(parsers.parse('I should see an empty state message "{msg}"'))
def check_empty_state(logged_in_page, msg):
    # Look for any element containing the empty state message
    page_text = logged_in_page.locator("body").text_content()
    assert msg.lower() in page_text.lower(), f"Empty state '{msg}' not found"


@then("I should not see any error messages")
def no_errors(logged_in_page):
    errors = logged_in_page.locator(".toast-error")
    assert errors.count() == 0


# ---------------------------------------------------------------------------
# Stat card assertions
# ---------------------------------------------------------------------------


@then(parsers.parse('I should see a stat card "{label}" with value "{value}"'))
def check_stat_card(logged_in_page, label, value):
    cards = logged_in_page.locator(".stat-card")
    for i in range(cards.count()):
        card = cards.nth(i)
        if label.lower() in card.text_content().lower():
            card_value = card.locator(".value").text_content().strip()
            assert card_value == value, (
                f"Stat '{label}' expected '{value}', got '{card_value}'"
            )
            return
    raise AssertionError(f"Stat card '{label}' not found")


@then(parsers.parse('I should see a stat card "{label}" with a numeric value'))
def check_stat_card_numeric(logged_in_page, label):
    cards = logged_in_page.locator(".stat-card")
    for i in range(cards.count()):
        card = cards.nth(i)
        if label.lower() in card.text_content().lower():
            card_value = card.locator(".value").text_content().strip()
            assert card_value.isdigit(), (
                f"Stat '{label}' value '{card_value}' is not numeric"
            )
            return
    raise AssertionError(f"Stat card '{label}' not found")


# ---------------------------------------------------------------------------
# Data setup helpers (create test data via live server)
# ---------------------------------------------------------------------------


@given(parsers.parse("{n:d} documents exist with various statuses"))
def create_documents_various(live_client, n):
    statuses = ["approved", "needs_review", "rejected"]
    docs = []
    for i in range(n):
        status = statuses[i % len(statuses)]
        r = live_client.post(
            "/api/documents/",
            json={
                "file_name": f"doc_{i:03d}.pdf",
                "status": status,
                "document_type": "packing_list",
            },
        )
        assert r.status_code in (200, 201), r.text
        docs.append(r.json())
    return docs


@given(parsers.parse("{n:d} documents exist"))
def create_n_documents(live_client, n):
    docs = []
    for i in range(n):
        r = live_client.post(
            "/api/documents/",
            json={
                "file_name": f"doc_{i:03d}.pdf",
                "status": "approved",
                "document_type": "packing_list",
            },
        )
        assert r.status_code in (200, 201), r.text
        docs.append(r.json())
    return docs


@given(parsers.parse("{n:d} vendors exist"))
def create_n_vendors(live_client, n):
    vendors = []
    for i in range(n):
        r = live_client.post("/api/vendors/", json={"name": f"Vendor {i}"})
        assert r.status_code in (200, 201), r.text
        vendors.append(r.json())
    return vendors


@given(parsers.parse("{n:d} orders exist"))
def create_n_orders(live_client, n):
    # Need a vendor first
    vr = live_client.post("/api/vendors/", json={"name": "Test Vendor for Orders"})
    vendor = vr.json()
    orders = []
    for i in range(n):
        r = live_client.post(
            "/api/orders/",
            json={
                "vendor_id": vendor["id"],
                "po_number": f"PO-TEST-{i:04d}",
                "status": "pending",
            },
        )
        assert r.status_code in (200, 201), r.text
        orders.append(r.json())
    return orders


@given(parsers.parse('{n:d} documents with status "{status}"'))
def create_documents_with_status(live_client, n, status):
    docs = []
    for i in range(n):
        r = live_client.post(
            "/api/documents/",
            json={
                "file_name": f"doc_{status}_{i:03d}.pdf",
                "status": status,
                "document_type": "packing_list",
            },
        )
        assert r.status_code in (200, 201), r.text
        docs.append(r.json())
    return docs


@given("the database is empty")
def empty_database():
    # In UI test isolation, database starts empty per test due to TRUNCATE cleanup
    pass


@given("documents exist")
def some_documents_exist(live_client):
    for i in range(3):
        live_client.post(
            "/api/documents/",
            json={
                "file_name": f"sample_{i}.pdf",
                "status": "needs_review",
                "document_type": "packing_list",
                "vendor_name": "Fisher Scientific",
            },
        )
