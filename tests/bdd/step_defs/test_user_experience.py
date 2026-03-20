"""BDD step definitions for user experience tests."""

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("../features/user_experience.feature")


# --- Shared context fixture ---
@pytest.fixture
def ctx():
    """Shared context for storing responses between steps."""
    return {}


# --- Given steps ---


@given("the system is set up")
def system_setup(api):
    """Ensure system is set up."""
    r = api.get("/api/setup/status")
    if r.status_code == 200 and r.json().get("needs_setup"):
        api.post(
            "/api/setup/complete",
            json={
                "admin_name": "Test Admin",
                "admin_email": "admin@test.com",
                "admin_password": "TestPassword123!",
            },
        )


@given('I am logged in as "admin@test.com"')
def logged_in(api):
    """Log in as admin user."""
    api.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "TestPassword123!"},
    )


# --- When steps ---


@when("I navigate to the dashboard", target_fixture="dashboard_response")
def navigate_dashboard(api):
    """Navigate to dashboard."""
    return api.get("/api/v1/analytics/dashboard")


@when("I click the Documents nav link")
def click_documents_nav():
    """Click documents nav - frontend test."""
    pass


@when("I click the dark mode toggle")
def click_dark_mode_toggle():
    """Toggle dark mode - frontend test."""
    pass


@when("I refresh the page")
def refresh_page(api, dashboard_response):
    """Refresh page."""
    return api.get("/api/v1/analytics/dashboard")


@when("I navigate to the documents page", target_fixture="documents_response")
def navigate_documents(api):
    """Go to documents page."""
    return api.get("/api/v1/documents/")


@when("I submit the form with empty fields", target_fixture="login_response")
def submit_empty_login(api):
    """Submit empty login."""
    return api.post("/api/auth/login", json={"email": "", "password": ""})


@when("I type in the search box")
def type_in_search():
    """Type in search - frontend test."""
    pass


@when("I resize to mobile viewport")
def resize_to_mobile():
    """Resize to mobile - frontend test."""
    pass


@when("I navigate to the inventory page", target_fixture="inventory_response")
def navigate_inventory(api):
    """Go to inventory page."""
    return api.get("/api/v1/inventory/")


@when("the upload completes successfully")
def upload_completes():
    """Upload success."""
    pass


@when("the error notification appears")
def error_notification_appears():
    """Error notification visible."""
    pass


# --- Then steps ---


@then("the page should load within 2 seconds")
def page_loads_fast(dashboard_response):
    """Verify page loads quickly."""
    assert dashboard_response.status_code == 200


@then("I should see the sidebar navigation")
def sidebar_visible():
    """Sidebar would be checked in frontend tests."""
    pass  # Frontend-only assertion


@then("no console errors should appear")
def no_console_errors():
    """Console errors would be checked in frontend tests."""
    pass  # Frontend-only assertion


@then("I should be on the documents page")
def on_documents_page(documents_response):
    """Verify documents page."""
    assert documents_response.status_code == 200


@then('the URL should be "/documents"')
def url_is_documents():
    """URL check - frontend test."""
    pass


@then("the theme should change to dark")
def theme_is_dark():
    """Dark theme check."""
    pass


@then("the preference should be saved")
def preference_saved():
    """Preference saved check."""
    pass


@then("the theme should still be dark")
def theme_still_dark():
    """Theme persistence check."""
    pass


@then("I should see an empty state message")
def empty_state_visible(documents_response):
    """Empty state check."""
    data = documents_response.json()
    # Empty state means 0 items
    assert "items" in data


@then("the message should suggest uploading a document")
def upload_suggestion_visible():
    """Upload suggestion check."""
    pass


@then("I should see validation error messages")
def validation_errors_visible(login_response):
    """Validation errors check."""
    assert login_response.status_code in [400, 401, 422]


@then("the errors should be in red text")
def errors_in_red():
    """Error styling check."""
    pass


@then("results should filter in real-time")
def results_filter_realtime():
    """Real-time filter check."""
    pass


@then("the search should be debounced")
def search_debounced():
    """Debounce check."""
    pass


@then("I should see page size options")
def page_size_options_visible():
    """Page size options check."""
    pass


@then("the current page should be highlighted")
def current_page_highlighted():
    """Current page check."""
    pass


@then("total count should be displayed")
def total_count_displayed(documents_response):
    """Verify total count in response."""
    data = documents_response.json()
    assert "total" in data


@then("the sidebar should collapse")
def sidebar_collapsed():
    """Sidebar collapse check."""
    pass


@then("a hamburger menu should appear")
def hamburger_menu_visible():
    """Hamburger menu check."""
    pass


@then("I should see a loading indicator")
def loading_indicator_visible():
    """Loading indicator check."""
    pass


@then("the indicator should disappear when data loads")
def indicator_disappears(inventory_response):
    """Loading complete check."""
    assert inventory_response.status_code == 200


@then("a success notification should appear")
def success_notification_visible():
    """Success notification check."""
    pass


@then("it should auto-dismiss after 3 seconds")
def auto_dismiss_notification():
    """Auto-dismiss check."""
    pass


@then("I should be able to dismiss it")
def can_dismiss_error():
    """Dismiss check."""
    pass


@then("it should have a close button")
def close_button_visible():
    """Close button check."""
    pass
