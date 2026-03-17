"""UI BDD test fixtures — Playwright browser hitting a real FastAPI server.

Extends the existing BDD conftest (PostgreSQL + Meilisearch via Docker).
Adds:
  - A live uvicorn server on a random port (per-session)
  - Playwright browser + page (per-test)
  - Auth helpers (login, logout)
  - Shared step definitions are in step_defs/ui_common.py

Database isolation strategy for UI tests:
  The live uvicorn server runs in a daemon thread with its own DB connections.
  Unlike API tests (which use savepoint rollback), UI tests commit data for
  real so the live server can see it, then TRUNCATE all tables after each test.
  Step definitions create test data by POSTing to the live server URL.
"""

import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from sqlmodel import text

# Re-export base engine fixture (used for table creation/teardown).
from tests.bdd.conftest import db_engine  # noqa: F401

# ---------------------------------------------------------------------------
# Live server
# ---------------------------------------------------------------------------

_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://labmanager:testpass@localhost:5432/labmanager_test",
)
os.environ["DATABASE_URL"] = _DB_URL
os.environ.setdefault("AUTH_ENABLED", "false")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _UvicornServer(threading.Thread):
    """Run uvicorn in a daemon thread so it dies with the test session."""

    def __init__(self, app, host: str, port: int):
        super().__init__(daemon=True)
        self.config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self.server = uvicorn.Server(self.config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


@pytest.fixture(scope="session")
def live_server(db_engine):  # noqa: F811
    """Start a real FastAPI server for Playwright to hit.

    The server uses the same test database as db_engine.  Data inserted via
    the server's API is committed for real; cleanup happens per-test via the
    ``_ui_db_cleanup`` autouse fixture.
    """
    port = _find_free_port()
    host = "127.0.0.1"

    os.environ["AUTH_ENABLED"] = "false"

    server = _UvicornServer("lab_manager.api.app:app", host, port)
    server.start()

    # Wait for server to accept connections
    base_url = f"http://{host}:{port}"
    for _ in range(50):
        try:
            r = httpx.get(f"{base_url}/api/health", timeout=1.0)
            if r.status_code in (200, 503):
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError(f"Live server did not start on {base_url}")

    yield base_url
    server.stop()


# ---------------------------------------------------------------------------
# Per-test database cleanup (truncate all tables after each UI test)
# ---------------------------------------------------------------------------

# Tables in dependency order (children first) to avoid FK violations.
_TRUNCATE_TABLES = [
    "consumption_log",
    "alerts",
    "audit_log",
    "inventory",
    "order_items",
    "documents",
    "orders",
    "products",
    "vendors",
    "staff",
    "locations",
]


@pytest.fixture(autouse=True)
def _ui_db_cleanup(db_engine):  # noqa: F811
    """Truncate all tables after each UI test for isolation.

    Uses TRUNCATE ... CASCADE so FK order doesn't matter, but we list tables
    explicitly to avoid touching alembic_version or other infrastructure tables.
    """
    yield
    with db_engine.connect() as conn:
        # TRUNCATE is DDL-like in PostgreSQL — fast and resets sequences.
        table_list = ", ".join(_TRUNCATE_TABLES)
        conn.execute(text(f"TRUNCATE {table_list} CASCADE"))
        conn.commit()


# ---------------------------------------------------------------------------
# HTTP client for step definitions to create data via the live server
# ---------------------------------------------------------------------------


@pytest.fixture
def live_client(live_server):
    """An httpx client pointed at the live server for data setup in steps."""
    with httpx.Client(base_url=live_server, timeout=10.0) as client:
        yield client


# ---------------------------------------------------------------------------
# Playwright browser fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_instance():
    """Launch a Playwright Chromium browser (session-scoped for speed)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip(
            "playwright not installed — run: uv pip install playwright && playwright install chromium"
        )

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def page(browser_instance):
    """A fresh browser page per test (isolates state)."""
    ctx = browser_instance.new_context(
        viewport={"width": 1280, "height": 800},
    )
    pg = ctx.new_page()
    yield pg
    pg.close()
    ctx.close()


@pytest.fixture
def logged_in_page(page, live_server):
    """A browser page that's already past the login screen.

    Since AUTH_ENABLED=false in test env, the app auto-shows the main UI.
    Just navigate to the app root and wait for it to load.
    """
    page.goto(live_server)
    # Wait for the main app to be visible (auth disabled = auto-login)
    page.wait_for_selector("#main-app", state="visible", timeout=5000)
    return page
