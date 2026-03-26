"""Step definitions for one-click lab setup BDD scenarios."""

from __future__ import annotations

import os

import pytest
from pytest_bdd import given, parsers, scenario, then, when
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.config import get_settings

FEATURE = "../features/one_click_setup.feature"

# --- Scenarios ---


@scenario(FEATURE, "Fresh deployment indicates setup is needed")
def test_fresh_setup_needed():
    pass


@scenario(FEATURE, "Setup status endpoint requires no authentication")
def test_setup_status_no_auth():
    pass


@scenario(FEATURE, "Config endpoint requires no authentication")
def test_config_no_auth():
    pass


@scenario(FEATURE, "Lab config returns configured branding")
def test_config_branding():
    pass


@scenario(FEATURE, "Lab config returns defaults when not configured")
def test_config_defaults():
    pass


@scenario(FEATURE, "Create admin account via setup wizard")
def test_create_admin():
    pass


@scenario(FEATURE, "Setup endpoint requires no authentication")
def test_setup_no_auth():
    pass


@scenario(FEATURE, "Invalid email is rejected")
def test_invalid_email():
    pass


@scenario(FEATURE, "Empty name is rejected")
def test_empty_name():
    pass


@scenario(FEATURE, "Password too short is rejected")
def test_password_too_short():
    pass


@scenario(FEATURE, "Password exceeding bcrypt 72-byte limit is rejected")
def test_password_too_long():
    pass


@scenario(FEATURE, "Setup blocked after first admin is created")
def test_setup_blocked():
    pass


@scenario(FEATURE, "Setup status shows false after admin exists")
def test_setup_status_after_admin():
    pass


@scenario(FEATURE, "Login works immediately after setup")
def test_login_after_setup():
    pass


@scenario(FEATURE, "Login with wrong password fails")
def test_login_wrong_password():
    pass


@scenario(FEATURE, "Session cookie is set after login")
def test_session_cookie():
    pass


@scenario(FEATURE, "Authenticated user can access protected endpoints")
def test_auth_me():
    pass


@scenario(FEATURE, "Logout clears session")
def test_logout():
    pass


# --- Shared context ---


@pytest.fixture
def ctx():
    """Shared context for passing data between steps."""
    return {}


# --- Test client helpers ---
# Setup tests need auth_enabled=true and a clean in-memory DB per scenario.


from contextlib import contextmanager  # noqa: E402


@contextmanager
def _setup_client(lab_name: str = "My Lab", lab_subtitle: str = ""):
    """Context manager: TestClient with auth enabled and fresh in-memory DB.

    Yields the client, then closes session/engine and restores env + DB state.
    """
    import lab_manager.database as db_module
    from lab_manager.api.app import create_app
    from lab_manager.api.deps import get_db

    env_overrides = {
        "AUTH_ENABLED": "true",
        "ADMIN_SECRET_KEY": "test-secret-key-for-signing",
        "SECURE_COOKIES": "false",
        "LAB_NAME": lab_name,
        "LAB_SUBTITLE": lab_subtitle,
    }
    orig_env = {k: os.environ.get(k) for k in env_overrides}
    for k, v in env_overrides.items():
        os.environ[k] = v
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    original_engine = db_module._engine
    original_factory = db_module._session_factory
    db_module._engine = engine
    db_module._session_factory = None

    app = create_app()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    from fastapi.testclient import TestClient

    try:
        with TestClient(app) as client:
            yield client
    finally:
        session.close()
        engine.dispose()
        db_module._engine = original_engine
        db_module._session_factory = original_factory
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


# --- Given steps ---


@given("a fresh Lab Manager instance with no users", target_fixture="api")
def fresh_instance():
    with _setup_client() as client:
        yield client


@given(
    parsers.parse(
        'a Lab Manager instance with name "{name}" and subtitle "{subtitle}"'
    ),
    target_fixture="api",
)
def instance_with_branding(name, subtitle):
    with _setup_client(lab_name=name, lab_subtitle=subtitle) as client:
        yield client


@given("a Lab Manager instance with default settings", target_fixture="api")
def instance_with_defaults():
    with _setup_client() as client:
        yield client


@given("a Lab Manager instance where setup was already completed", target_fixture="api")
def instance_setup_done():
    with _setup_client() as client:
        client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": "Dr. Admin",
                "admin_email": "admin@lab.org",
                "admin_password": "securepass123",
            },
        )
        yield client


@given(
    parsers.parse(
        'a Lab Manager instance where setup was completed by "{name}" with email "{email}" and password "{password}"'
    ),
    target_fixture="api",
)
def instance_setup_done_by(name, email, password):
    with _setup_client() as client:
        client.post(
            "/api/v1/setup/complete",
            json={
                "admin_name": name,
                "admin_email": email,
                "admin_password": password,
            },
        )
        yield client


@given(parsers.parse('I am logged in as "{email}" with password "{password}"'))
def logged_in(api, ctx, email, password):
    resp = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed during setup: {resp.text}"


# --- When steps ---


@when("I check the setup status")
def check_setup_status(api, ctx):
    ctx["response"] = api.get("/api/v1/setup/status")


@when("I check the setup status without any credentials")
def check_setup_status_no_creds(api, ctx):
    ctx["response"] = api.get("/api/v1/setup/status")


@when("I request the lab configuration without any credentials")
def request_config_no_creds(api, ctx):
    ctx["response"] = api.get("/api/v1/config")


@when("I request the lab configuration")
def request_config(api, ctx):
    ctx["response"] = api.get("/api/v1/config")


@when(
    parsers.parse(
        'I complete setup with name "{name}" email "{email}" and password "{password}"'
    )
)
def complete_setup(api, ctx, name, email, password):
    ctx["response"] = api.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": name,
            "admin_email": email,
            "admin_password": password,
        },
    )


@when("I complete setup with a 73-byte password")
def complete_setup_long_password(api, ctx):
    long_password = "A" * 73
    ctx["response"] = api.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": "Dr. Chen",
            "admin_email": "admin@example.com",
            "admin_password": long_password,
        },
    )


@when(
    parsers.parse(
        'I try to complete setup again with name "{name}" email "{email}" and password "{password}"'
    )
)
def try_setup_again(api, ctx, name, email, password):
    ctx["response"] = api.post(
        "/api/v1/setup/complete",
        json={
            "admin_name": name,
            "admin_email": email,
            "admin_password": password,
        },
    )


@when(parsers.parse('I log in with email "{email}" and password "{password}"'))
def do_login(api, ctx, email, password):
    ctx["response"] = api.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


@when("I check my auth status")
def check_auth_me(api, ctx):
    ctx["response"] = api.get("/api/v1/auth/me")


@when("I log out")
def do_logout(api, ctx):
    ctx["response"] = api.post("/api/v1/auth/logout")


# --- Then steps ---


@then("the response should indicate setup is needed")
def setup_needed(ctx):
    resp = ctx["response"]
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is True


@then("the response should indicate setup is not needed")
def setup_not_needed(ctx):
    resp = ctx["response"]
    assert resp.status_code == 200
    assert resp.json()["needs_setup"] is False


@then("I should not receive a 401 unauthorized error")
def not_401(ctx):
    assert ctx["response"].status_code != 401


@then(parsers.parse('the lab name should be "{name}"'))
def check_lab_name(ctx, name):
    assert ctx["response"].json()["lab_name"] == name


@then(parsers.parse('the lab subtitle should be "{subtitle}"'))
def check_lab_subtitle(ctx, subtitle):
    assert ctx["response"].json()["lab_subtitle"] == subtitle


@then("the lab subtitle should be empty")
def check_lab_subtitle_empty(ctx):
    assert ctx["response"].json()["lab_subtitle"] == ""


@then("the setup should succeed")
def setup_succeeded(ctx):
    resp = ctx["response"]
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@then("the setup status should no longer indicate setup is needed")
def setup_no_longer_needed(api, ctx):
    resp = api.get("/api/v1/setup/status")
    assert resp.json()["needs_setup"] is False


@then(parsers.parse("the setup should fail with status {status:d}"))
def setup_failed_with_status(ctx, status):
    assert ctx["response"].status_code == status


@then(parsers.parse('the error should mention "{text}"'))
def error_mentions(ctx, text):
    detail = ctx["response"].json().get("detail", "")
    assert text in detail, f"Expected '{text}' in '{detail}'"


@then("the login should succeed")
def login_succeeded(ctx):
    resp = ctx["response"]
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@then(parsers.parse('the logged-in user name should be "{name}"'))
def logged_in_user_name(ctx, name):
    assert ctx["response"].json()["user"]["name"] == name


@then(parsers.parse("the login should fail with status {status:d}"))
def login_failed(ctx, status):
    assert ctx["response"].status_code == status


@then("a session cookie should be set")
def session_cookie_set(ctx):
    resp = ctx["response"]
    cookies = resp.headers.get_list("set-cookie")
    assert any("lab_session" in c for c in cookies), (
        "Expected lab_session cookie to be set"
    )


@then(parsers.parse('I should be recognized as "{name}"'))
def recognized_as(ctx, name):
    resp = ctx["response"]
    assert resp.status_code == 200
    assert resp.json()["user"]["name"] == name


@then("the logout should succeed")
def logout_succeeded(ctx):
    assert ctx["response"].status_code == 200


@then("checking my auth status should return 401")
def auth_me_returns_401(api, ctx):
    api.cookies.clear()
    resp = api.get("/api/v1/auth/me")
    assert resp.status_code == 401
