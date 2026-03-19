"""FastAPI application factory."""

from __future__ import annotations

import hmac
import logging
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import text

from lab_manager.api.admin import setup_admin
from lab_manager.config import get_settings
from lab_manager.database import get_engine
from lab_manager.exceptions import BusinessError
from lab_manager.logging_config import configure_logging

# Import to register SQLAlchemy event listeners on module load.
import lab_manager.services.audit as _audit_svc  # noqa: F401

configure_logging()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"
SCANS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "shenlab-docs"

# Strip control characters from X-User header to prevent log injection.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_USER_LEN = 100

# Paths that never require authentication.
_AUTH_ALLOWLIST = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/sw.js",
    "/manifest.json",
}
_AUTH_ALLOWLIST_PREFIXES = (
    "/admin/",  # SQLAdmin has its own authentication backend
    "/static/",  # Frontend assets (login page needs CSS/JS before auth)
)

# Session cookie config
_SESSION_COOKIE = "lab_session"
_SESSION_MAX_AGE = 86400  # 24 hours


def _get_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    if not settings.admin_secret_key:
        raise RuntimeError(
            "ADMIN_SECRET_KEY must be set when auth is enabled. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return URLSafeTimedSerializer(settings.admin_secret_key, salt="lab-session")


def create_app() -> FastAPI:
    settings = get_settings()
    # Ensure upload directory exists at startup (not per-request in health check)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    # Disable interactive docs in production (exposes full API schema)
    docs_kwargs = {}
    if settings.auth_enabled:
        docs_kwargs = dict(docs_url=None, redoc_url=None, openapi_url=None)
    app = FastAPI(
        title="LabClaw Lab Manager",
        description="Lab inventory management with OCR document intake",
        version="0.1.5",
        **docs_kwargs,
    )

    # --- Domain exception → HTTP response handler ---
    @app.exception_handler(BusinessError)
    async def _business_error_handler(request: Request, exc: BusinessError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    # --- Audit middleware (inner — registered first) ---
    #
    # In Starlette, last-registered middleware is outermost. Registering audit
    # first makes it inner: auth runs first (sets request.state.user), then
    # audit reads it and sets the audit context for SQLAlchemy event listeners.
    #
    @app.middleware("http")
    async def audit_middleware(request: Request, call_next):
        from lab_manager.logging_config import generate_request_id, request_id_var

        request_id = generate_request_id()
        try:
            user = getattr(request.state, "user", "system")
            _audit_svc.set_current_user(user)
            try:
                response = await call_next(request)
            finally:
                _audit_svc.set_current_user(None)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.set(None)

    # --- Auth middleware (outer — registered second, runs first) ---
    #
    #   1. Allowlisted paths → skip auth
    #   2. auth_enabled=True:
    #      a. Check session cookie → load Staff → verify is_active
    #      b. Fallback: check X-Api-Key header (programmatic access)
    #      c. Neither → 401
    #   3. auth_enabled=False (dev mode):
    #      a. Read X-User header for audit context
    #
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        settings = get_settings()
        user = "system"

        # Allowlisted paths — no auth required.
        is_allowed = path in _AUTH_ALLOWLIST or path.startswith(
            _AUTH_ALLOWLIST_PREFIXES
        )

        if settings.auth_enabled and not is_allowed:
            authenticated = False

            # 1. Try session cookie
            session_cookie = request.cookies.get(_SESSION_COOKIE)
            if session_cookie:
                try:
                    serializer = _get_serializer()
                    data = serializer.loads(session_cookie, max_age=_SESSION_MAX_AGE)
                    staff_id = data.get("staff_id")
                    staff_name = data.get("name", "unknown")

                    from lab_manager.database import get_db_session

                    with get_db_session() as db:
                        from lab_manager.models.staff import Staff

                        staff = db.get(Staff, staff_id)
                        if staff and staff.is_active:
                            user = staff.name
                            authenticated = True
                        else:
                            logger.warning(
                                "Session for inactive/missing staff_id=%s name=%s",
                                staff_id,
                                staff_name,
                            )
                except BadSignature:
                    logger.warning("Invalid session cookie signature")

            # 2. Fallback: API key header
            if not authenticated:
                api_key = request.headers.get("X-Api-Key", "")
                if settings.api_key and api_key:
                    if hmac.compare_digest(api_key, settings.api_key):
                        user = request.headers.get("X-User", "api-client")
                        user = _CONTROL_CHARS.sub("", user)[:_MAX_USER_LEN]
                        authenticated = True

            if not authenticated:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"},
                )
        elif not settings.auth_enabled:
            raw = request.headers.get("X-User", "system")
            user = _CONTROL_CHARS.sub("", raw)[:_MAX_USER_LEN]

        request.state.user = user
        return await call_next(request)

    # --- Health endpoint (no auth required — in allowlist) ---

    @app.get("/api/health")
    def health():
        checks: dict[str, str] = {}

        # PostgreSQL: SELECT 1
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            checks["postgresql"] = "ok"
        except Exception as e:
            logger.error("Health check: PostgreSQL failed: %s", e)
            checks["postgresql"] = "error"

        # Meilisearch
        try:
            from lab_manager.services.search import get_search_client

            client = get_search_client()
            client.health()
            checks["meilisearch"] = "ok"
        except Exception as e:
            logger.error("Health check: Meilisearch failed: %s", e)
            checks["meilisearch"] = "error"

        # VLM/LLM: config-only check — Gemini or OpenAI key suffices
        settings = get_settings()
        has_llm_key = bool(settings.extraction_api_key or settings.openai_api_key)
        checks["llm"] = "ok" if has_llm_key else "not configured"

        # Disk space: warn if uploads partition has less than 500MB free
        try:
            usage = shutil.disk_usage(settings.upload_dir)
            free_mb = usage.free / (1024 * 1024)
            checks["disk"] = "ok" if free_mb >= 500 else "warning"
        except Exception as e:
            logger.error("Health check: disk check failed: %s", e)
            checks["disk"] = "error"

        # Only core services (postgresql, meilisearch) can degrade health.
        # LLM and disk are informational — don't take service out of rotation.
        core = {k: v for k, v in checks.items() if k in ("postgresql", "meilisearch")}
        all_ok = all(v == "ok" for v in core.values())
        return JSONResponse(
            {"status": "ok" if all_ok else "degraded", "services": checks},
            status_code=200 if all_ok else 503,
        )

    # --- Auth endpoints ---

    from fastapi import Body

    @app.post("/api/auth/login")
    def login(
        email: str = Body(...),
        password: str = Body(...),
    ):
        import bcrypt as _bcrypt

        from lab_manager.database import get_db_session
        from lab_manager.models.staff import Staff

        try:
            with get_db_session() as db:
                staff = db.query(Staff).filter(Staff.email == email).first()
        except Exception:
            logger.error("Login: database unavailable")
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily unavailable"},
            )

        # Constant-time: always run bcrypt to prevent timing oracle on user existence.
        _DUMMY_HASH = b"$2b$12$LJ3m4ys3Lg2VBe7MaBSW2.P68rAGkMgGMfkCGKEKeDqz4rMpWsSi6"
        password_ok = False
        if staff and staff.is_active and staff.password_hash:
            password_ok = _bcrypt.checkpw(
                password.encode("utf-8"), staff.password_hash.encode("utf-8")
            )
        else:
            _bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)

        if not password_ok:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid email or password"},
            )

        # Create signed session cookie with new token (session regeneration)
        serializer = _get_serializer()
        session_data = serializer.dumps({"staff_id": staff.id, "name": staff.name})
        response = JSONResponse(
            {"status": "ok", "user": {"id": staff.id, "name": staff.name}}
        )
        response.set_cookie(
            _SESSION_COOKIE,
            session_data,
            max_age=_SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=get_settings().secure_cookies,
        )
        logger.info("Login successful for %s (staff_id=%s)", staff.email, staff.id)
        return response

    @app.get("/api/auth/me")
    def auth_me(request: Request):
        """Return current user info from session cookie. Used by frontend to check auth state."""
        settings = get_settings()
        if not settings.auth_enabled:
            return {"user": {"id": 0, "name": "Lab User"}}
        session_cookie = request.cookies.get(_SESSION_COOKIE)
        if not session_cookie:
            return JSONResponse(
                status_code=401, content={"detail": "Not authenticated"}
            )
        try:
            serializer = _get_serializer()
            data = serializer.loads(session_cookie, max_age=_SESSION_MAX_AGE)
            return {
                "user": {"id": data.get("staff_id"), "name": data.get("name", "User")}
            }
        except BadSignature:
            return JSONResponse(status_code=401, content={"detail": "Invalid session"})

    @app.post("/api/auth/logout")
    def logout():
        response = JSONResponse({"status": "ok"})
        response.delete_cookie(_SESSION_COOKIE)
        return response

    # Register route modules
    from lab_manager.api.routes import (
        alerts,
        analytics,
        ask,
        audit,
        documents,
        export,
        inventory,
        orders,
        products,
        search,
        vendors,
    )

    # Auth is handled by auth_middleware — no per-route dependency needed.
    api_router = APIRouter()
    api_router.include_router(vendors.router, prefix="/api/vendors", tags=["vendors"])
    api_router.include_router(
        products.router, prefix="/api/products", tags=["products"]
    )
    api_router.include_router(orders.router, prefix="/api/orders", tags=["orders"])
    api_router.include_router(
        inventory.router, prefix="/api/inventory", tags=["inventory"]
    )
    api_router.include_router(
        documents.router, prefix="/api/documents", tags=["documents"]
    )
    api_router.include_router(search.router, prefix="/api/search", tags=["search"])
    api_router.include_router(ask.router, prefix="/api/ask", tags=["ask"])
    api_router.include_router(
        analytics.router, prefix="/api/analytics", tags=["analytics"]
    )
    api_router.include_router(export.router, prefix="/api/export", tags=["export"])
    api_router.include_router(audit.router, prefix="/api/audit", tags=["audit"])
    api_router.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
    app.include_router(api_router)

    # Serve scan images (protected by auth middleware when auth is enabled)
    if SCANS_DIR.exists():
        app.mount("/scans", StaticFiles(directory=str(SCANS_DIR)), name="scans")

    # Serve uploaded documents at /uploads/
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/uploads",
        StaticFiles(directory=str(upload_path)),
        name="uploads",
    )

    # Wire up SQLAdmin UI at /admin/
    setup_admin(app, get_engine())

    # PWA: service worker must be served from root for scope
    @app.get("/sw.js")
    def service_worker():
        return FileResponse(
            STATIC_DIR / "sw.js",
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/"},
        )

    @app.get("/manifest.json")
    def manifest():
        return FileResponse(
            STATIC_DIR / "manifest.json",
            media_type="application/manifest+json",
        )

    # Serve frontend static assets and root
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
