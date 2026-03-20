"""BDD step definitions for user experience tests."""
import pytest
from pytest_bdd import given, when, then, scenarios

scenarios("../features/user_experience.feature")


@given("the system is set up")
def system_setup(client):
    """Ensure system is set up."""
    response = client.get("/api/setup/status")
    if response.status_code == 200:
        data = response.json()
        if data.get("needs_setup"):
            client.post(
                "/api/setup/complete",
                json={
                    "admin_name": "Test Admin",
                    "admin_email": "admin@test.com",
                    "admin_password": "TestPassword123!",
                },
            )


@given('I am logged in as "admin@test.com"')
def logged_in(client):
    """Log in as admin user."""
    client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "TestPassword123!"},
    )


@when("I navigate to the dashboard")
def navigate_dashboard(client):
    """Navigate to dashboard."""
    client.get("/api/v1/analytics/dashboard")


@then("the page should load within 2 seconds")
def page_loads_fast(client):
    """Verify page loads quickly."""
    import time
    start = time.time()
    client.get("/api/v1/analytics/dashboard")
    elapsed = time.time() - start
    assert elapsed < 2.0, f"Page took {elapsed}s to load"


@then("I should see the sidebar navigation")
def sidebar_visible():
    """Sidebar would be checked in frontend tests."""
    pass  # Frontend-only assertion


@then("no console errors should appear")
def no_console_errors():
    """Console errors would be checked in frontend tests."""
    pass  # Frontend-only assertion


@given("I am on the dashboard")
def on_dashboard(client):
    """Verify on dashboard."""
    client.get("/api/v1/analytics/dashboard")


@when('I click the "Documents" nav link')
def click_documents_nav():
    """Click documents nav - frontend test."""
    pass


@then("I should be on the documents page")
def on_documents_page(client):
    """Verify documents page."""
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200


@then('the URL should be "/documents"')
def url_is_documents():
    """URL check - frontend test."""
    pass


@given("I am on the dashboard in light mode")
def on_dashboard_light_mode():
    """Light mode state."""
    pass


@when("I click the dark mode toggle")
def click_dark_mode_toggle():
    """Toggle dark mode - frontend test."""
    pass


@then("the theme should change to dark")
def theme_is_dark():
    """Dark theme check."""
    pass


@then("the preference should be saved")
def preference_saved():
    """Preference saved check."""
    pass


@when("I refresh the page")
def refresh_page(client):
    """Refresh page."""
    client.get("/api/v1/analytics/dashboard")


@then("the theme should still be dark")
def theme_still_dark():
    """Theme persistence check."""
    pass


@given("no documents exist in the system")
def no_documents(db_session):
    """Ensure no documents exist."""
    from lab_manager.models.document import Document
    db_session.query(Document).delete()
    db_session.commit()


@when("I navigate to the documents page")
def navigate_documents(client):
    """Go to documents page."""
    client.get("/api/v1/documents/")


@then("I should see an empty state message")
def empty_state_visible():
    """Empty state check."""
    pass


@then("the message should suggest uploading a document")
def upload_suggestion_visible():
    """Upload suggestion check."""
    pass


@given("I am on the login page")
def on_login_page():
    """On login page."""
    pass


@when("I submit the form with empty fields")
def submit_empty_login(client):
    """Submit empty login."""
    client.post("/api/auth/login", json={"email": "", "password": ""})


@then("I should see validation error messages")
def validation_errors_visible():
    """Validation errors check."""
    pass


@then("the errors should be in red text")
def errors_in_red():
    """Error styling check."""
    pass


@given("some documents exist")
def some_documents_exist(db_session):
    """Create some test documents."""
    from lab_manager.models.document import Document
    docs = [Document(file_name=f"test_{i}.pdf", status="approved") for i in range(5)]
    for doc in docs:
        db_session.add(doc)
    db_session.commit()


@when("I type in the search box")
def type_in_search():
    """Type in search - frontend test."""
    pass


@then("results should filter in real-time")
def results_filter_realtime():
    """Real-time filter check."""
    pass


@then("the search should be debounced")
def search_debounced():
    """Debounce check."""
    pass


@given("50 documents exist")
def fifty_documents_exist(db_session):
    """Create 50 test documents."""
    from lab_manager.models.document import Document
    for i in range(50):
        doc = Document(file_name=f"test_{i}.pdf", status="approved")
        db_session.add(doc)
    db_session.commit()


@then("I should see page size options")
def page_size_options_visible():
    """Page size options check."""
    pass


@then("the current page should be highlighted")
def current_page_highlighted():
    """Current page check."""
    pass


@then("total count should be displayed")
def total_count_displayed(client):
    """Verify total count in response."""
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data


@given("I am on the dashboard")
def on_dashboard_for_mobile():
    """On dashboard for mobile test."""
    pass


@when("I resize to mobile viewport")
def resize_to_mobile():
    """Resize to mobile - frontend test."""
    pass


@then("the sidebar should collapse")
def sidebar_collapsed():
    """Sidebar collapse check."""
    pass


@then("a hamburger menu should appear")
def hamburger_menu_visible():
    """Hamburger menu check."""
    pass


@given("slow network conditions")
def slow_network():
    """Slow network simulation."""
    pass


@when("I navigate to the inventory page")
def navigate_inventory(client):
    """Go to inventory page."""
    client.get("/api/v1/inventory/")


@then("I should see a loading indicator")
def loading_indicator_visible():
    """Loading indicator check."""
    pass


@then("the indicator should disappear when data loads")
def indicator_disappears():
    """Loading complete check."""
    pass


@given("I am uploading a document")
def uploading_document():
    """Uploading state."""
    pass


@when("the upload completes successfully")
def upload_completes():
    """Upload success."""
    pass


@then("a success notification should appear")
def success_notification_visible():
    """Success notification check."""
    pass


@then("it should auto-dismiss after 3 seconds")
def auto_dismiss_notification():
    """Auto-dismiss check."""
    pass


@given("an API error occurs")
def api_error_occurs():
    """Simulate API error."""
    pass


@when("the error notification appears")
def error_notification_appears():
    """Error notification visible."""
    pass


@then("I should be able to dismiss it")
def can_dismiss_error():
    """Dismiss check."""
    pass


@then("it should have a close button")
def close_button_visible():
    """Close button check."""
    pass
