"""FastAPI application factory."""

from __future__ import annotations

import hmac
import logging
import re
import shutil
import time
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, URLSafeTimedSerializer
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select, text
from starlette.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Import to register SQLAlchemy event listeners on module load.
import lab_manager.services.audit as _audit_svc  # noqa: F401
from lab_manager.api.admin import setup_admin
from lab_manager.api.deps import get_db
from lab_manager.config import get_settings
from lab_manager.database import get_engine
from lab_manager.exceptions import BusinessError
from lab_manager.logging_config import configure_logging

logger = logging.getLogger(__name__)

access_logger = structlog.get_logger("lab_manager.api.access")

STATIC_DIR = Path(__file__).parent.parent / "static"


def _spa_assets_ready(static_dir: Path) -> bool:
    """Only enable SPA mode when the built asset set is complete."""
    dist_dir = static_dir / "dist"
    index_path = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"

    if not index_path.is_file() or not assets_dir.is_dir():
        return False

    html = index_path.read_text(encoding="utf-8")
    asset_refs = re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)["\']', html)
    if not asset_refs:
        return False

    js_refs = [ref for ref in asset_refs if ref.endswith(".js")]
    if not js_refs:
        return False

    return all((dist_dir / ref.lstrip("/")).is_file() for ref in asset_refs)


# Strip control characters from X-User header to prevent log injection.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_USER_LEN = 100

# Paths that never require authentication.
_AUTH_ALLOWLIST = {
    "/",
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/setup/status",
    "/api/setup/complete",
    "/api/config",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/setup/status",
    "/api/v1/setup/complete",
    "/api/v1/config",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/sw.js",
    "/manifest.json",
    "/favicon.svg",
    "/icons.svg",
}
_AUTH_ALLOWLIST_PREFIXES = (
    "/admin/",  # SQLAdmin has its own authentication backend
    "/static/",  # Frontend assets (login page needs CSS/JS before auth)
    "/assets/",  # SPA build assets (JS/CSS bundles)
    "/icons/",  # Icon assets
    "/api/v1/team/join/",  # Invitation acceptance (public, token-verified)
)

# Session cookie config
_SESSION_COOKIE = "lab_session"
_SESSION_MAX_AGE = 86400  # 24 hours
_MAX_JSON_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    if not settings.admin_secret_key:
        raise RuntimeError(
            "ADMIN_SECRET_KEY must be set when auth is enabled. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return URLSafeTimedSerializer(settings.admin_secret_key, salt="lab-session")


def _load_session_staff(session_cookie: str):
    """Load staff from session cookie, returning a detach-safe dict.

    Returns ``{"id": ..., "name": ..., "role": ..., "role_level": ...}``
    or *None*.  Eagerly extracts attributes inside the DB session so
    callers never hit a ``DetachedInstanceError``.
    """
    from datetime import datetime, timezone

    serializer = _get_serializer()
    data = serializer.loads(session_cookie, max_age=_SESSION_MAX_AGE)
    staff_id = data.get("staff_id")
    staff_name = data.get("name", "unknown")

    from lab_manager.database import get_db_session

    with get_db_session() as db:
        from lab_manager.models.staff import Staff

        staff = db.get(Staff, staff_id)
        if staff and staff.is_active:
            now_utc = datetime.now(timezone.utc)

            # Check account lock
            if staff.locked_until:
                locked = staff.locked_until
                if locked.tzinfo is None:
                    locked = locked.replace(tzinfo=timezone.utc)
                if locked > now_utc:
                    logger.warning(
                        "Session for locked staff_id=%s name=%s",
                        staff_id,
                        staff_name,
                    )
                    return None
            # Check access expiration
            if staff.access_expires_at:
                expires = staff.access_expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires < now_utc:
                    logger.warning(
                        "Session for expired-access staff_id=%s name=%s",
                        staff_id,
                        staff_name,
                    )
                    return None
            # Eagerly read attributes while session is open
            return {
                "id": staff.id,
                "name": staff.name,
                "email": staff.email,
                "role": staff.role,
                "role_level": staff.role_level,
            }

    logger.warning(
        "Session for inactive/missing staff_id=%s name=%s",
        staff_id,
        staff_name,
    )
    return None


def create_app() -> FastAPI:
    # Rebind logging to the current stderr for each app instance. Test suites
    # build many transient apps and capture streams; keeping the first stream
    # handler around causes later requests to log into closed file objects.
    configure_logging()
    settings = get_settings()
    # Ensure upload directory exists at startup (not per-request in health check)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    scans_dir = Path(settings.scans_dir).expanduser() if settings.scans_dir else None
    devices_dir = (
        Path(settings.devices_dir).expanduser() if settings.devices_dir else None
    )
    # Disable interactive docs in production (exposes full API schema)
    docs_kwargs = {}
    if settings.auth_enabled:
        docs_kwargs = dict(docs_url=None, redoc_url=None, openapi_url=None)
    app = FastAPI(
        title="LabClaw Lab Manager",
        description="Lab inventory management with OCR document intake",
        version="0.1.9",
        redirect_slashes=False,
        **docs_kwargs,
    )

    # Trust X-Forwarded-* headers only from loopback (reverse proxy on same host)
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "::1"])

    # --- CORS middleware (for development and cross-origin access) ---
    #   - Development (auth_enabled=false): Allow all origins for flexibility
    #   - Production (auth_enabled=true): Strict same-origin, proxy handles CORS
    #   - Handles preflight OPTIONS requests automatically
    #   - Allows credentials (cookies) for authenticated requests
    #
    settings = get_settings()
    # In dev mode (auth disabled), allow all origins for flexibility
    # In production (auth enabled), rely on reverse proxy for CORS
    if settings.auth_enabled:
        # Production: strict same-origin, reverse proxy handles CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    else:
        # Development: allow all origins, but without credentials (spec forbids * + credentials)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_size_guard(request: Request, call_next):
        content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
        content_length = request.headers.get("content-length")
        if (
            request.method in {"POST", "PUT", "PATCH"}
            and content_type == "application/json"
            and content_length
            and content_length.isdigit()
            and int(content_length) > _MAX_JSON_BODY_BYTES
        ):
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"JSON request body too large ({content_length} bytes). "
                        f"Maximum: {_MAX_JSON_BODY_BYTES} bytes (10 MB)."
                    )
                },
            )
        return await call_next(request)

    # --- Rate limiting (slowapi) ---
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "60"},
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

        staff_dict = None
        if settings.auth_enabled and not is_allowed:
            authenticated = False

            # 1. Try session cookie
            session_cookie = request.cookies.get(_SESSION_COOKIE)
            if session_cookie:
                try:
                    staff_dict = _load_session_staff(session_cookie)
                    if staff_dict:
                        user = staff_dict["name"]
                        authenticated = True
                except BadSignature:
                    logger.warning("Invalid session cookie signature")

            # 2. Fallback: API key header (X-User forbidden when auth_enabled=True)
            if not authenticated:
                api_key = request.headers.get("X-Api-Key", "")
                if settings.api_key and api_key:
                    if hmac.compare_digest(api_key, settings.api_key):
                        # When auth is enabled, API key clients are always "api-client"
                        # X-User header is ignored to prevent spoofing
                        user = "api-client"
                        staff_dict = {
                            "id": 0,
                            "name": "api-client",
                            "email": None,
                            "role": "admin",
                            "role_level": 1,
                        }
                        authenticated = True

            if not authenticated:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"},
                )
        elif not settings.auth_enabled:
            raw = request.headers.get("X-User", "system")
            user = _CONTROL_CHARS.sub("", raw)[:_MAX_USER_LEN]
            staff_dict = {
                "id": 0,
                "name": user,
                "email": None,
                "role": "pi",
                "role_level": 0,
            }

        request.state.user = user
        request.state.staff = staff_dict
        return await call_next(request)

    # --- Access log middleware (outermost — registered last, runs first) ---
    @app.middleware("http")
    async def access_log(request: Request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        access_logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

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
        has_llm_key = bool(
            settings.extraction_api_key
            or settings.openai_api_key
            or settings.rag_api_key
            or settings.nvidia_build_api_key
        )
        checks["llm"] = "ok" if has_llm_key else "not configured"

        # Disk space: warn if uploads partition has less than 500MB free
        try:
            usage = shutil.disk_usage(settings.upload_dir)
            free_mb = usage.free / (1024 * 1024)
            checks["disk"] = "ok" if free_mb >= 500 else "warning"
        except Exception as e:
            logger.error("Health check: disk check failed: %s", e)
            checks["disk"] = "error"

        # Only PostgreSQL is truly core — without it the app can't serve any data.
        # Meilisearch is important but starts independently (especially on managed
        # platforms like DO App Platform) and shouldn't take the app out of rotation.
        core = {k: v for k, v in checks.items() if k in ("postgresql",)}
        all_ok = all(v == "ok" for v in core.values())
        return JSONResponse(
            {"status": "ok" if all_ok else "degraded", "services": checks},
            status_code=200 if all_ok else 503,
        )

    # --- Auth endpoints ---

    from fastapi import Body

    @app.post("/api/auth/login", include_in_schema=False)
    @app.post("/api/v1/auth/login")
    @limiter.limit("5/minute")
    def login(
        request: Request,
        email: str = Body(...),
        password: str = Body(...),
        db=Depends(get_db),
    ):
        import bcrypt as _bcrypt
        from datetime import datetime, timezone

        from lab_manager.api.auth import get_permissions
        from lab_manager.models.staff import Staff

        try:
            staff = db.scalars(select(Staff).where(Staff.email == email)).first()
            # Eagerly load attributes before session closes
            if staff:
                staff_id = staff.id
                staff_name = staff.name
                staff_email = staff.email
                staff_role = staff.role
                staff_role_level = staff.role_level
                staff_active = staff.is_active
                staff_pw_hash = staff.password_hash
                staff_locked_until = staff.locked_until
            else:
                staff_id = staff_name = staff_email = staff_pw_hash = None
                staff_role = "visitor"
                staff_role_level = 4
                staff_active = False
                staff_locked_until = None
        except Exception:
            logger.error("Login: database unavailable")
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily unavailable"},
            )

        # Check account lock
        if staff_locked_until and staff_locked_until > datetime.now(timezone.utc):
            return JSONResponse(
                status_code=403,
                content={"detail": "Account temporarily locked. Try again later."},
            )

        # Constant-time: always run bcrypt to prevent timing oracle on user existence.
        _DUMMY_HASH = b"$2b$12$LJ3m4ys3Lg2VBe7MaBSW2.P68rAGkMgGMfkCGKEKeDqz4rMpWsSi6"
        password_ok = False
        if staff and staff_active and staff_pw_hash:
            password_ok = _bcrypt.checkpw(
                password.encode("utf-8"), staff_pw_hash.encode("utf-8")
            )
        else:
            _bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)

        if not password_ok:
            # Increment failed login count
            if staff:
                try:
                    from lab_manager.database import get_db_session as _fdb

                    with _fdb() as fdb:
                        s = fdb.get(Staff, staff_id)
                        if s:
                            s.failed_login_count = (s.failed_login_count or 0) + 1
                            # Lock after 5 consecutive failures for 15 minutes
                            if s.failed_login_count >= 5:
                                from datetime import timedelta

                                s.locked_until = datetime.now(timezone.utc) + timedelta(
                                    minutes=15
                                )
                            fdb.commit()
                except Exception:
                    logger.warning("Failed to update failed_login_count")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid email or password"},
            )

        # Create signed session cookie with new token (session regeneration)
        serializer = _get_serializer()
        session_data = serializer.dumps({"staff_id": staff_id, "name": staff_name})
        perms = get_permissions(staff_role)
        response = JSONResponse(
            {
                "status": "ok",
                "user": {
                    "id": staff_id,
                    "name": staff_name,
                    "role": staff_role,
                    "role_level": staff_role_level,
                    "permissions": sorted(perms),
                },
            }
        )
        response.set_cookie(
            _SESSION_COOKIE,
            session_data,
            max_age=_SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=get_settings().secure_cookies,
        )
        logger.info("Login successful for %s (staff_id=%s)", staff_email, staff_id)

        # Update last_login_at and reset failed_login_count
        from lab_manager.database import get_db_session as _get_db_session

        try:
            with _get_db_session() as _db:
                s = _db.get(Staff, staff_id)
                if s:
                    s.last_login_at = datetime.now(timezone.utc)
                    s.failed_login_count = 0
                    s.locked_until = None
                _db.commit()
        except Exception:
            logger.warning("Failed to update last_login_at")

        # Record login usage event for DAU measurement
        from lab_manager.models.usage_event import UsageEvent as _UsageEvent

        try:
            with _get_db_session() as _db:
                _db.add(
                    _UsageEvent(
                        user_email=staff_email,
                        event_type="login",
                        page="/login",
                    )
                )
                _db.commit()
        except Exception:
            logger.warning("Failed to record login usage event")
        return response

    @app.get("/api/auth/me", include_in_schema=False)
    @app.get("/api/v1/auth/me")
    def auth_me(request: Request):
        """Return current user info from session cookie. Used by frontend to check auth state."""
        from lab_manager.api.auth import get_permissions

        settings = get_settings()
        if not settings.auth_enabled:
            perms = get_permissions("pi")
            return {
                "user": {
                    "id": 0,
                    "name": "Lab User",
                    "email": None,
                    "role": "pi",
                    "role_level": 0,
                    "permissions": sorted(perms),
                }
            }
        session_cookie = request.cookies.get(_SESSION_COOKIE)
        if not session_cookie:
            return JSONResponse(
                status_code=401, content={"detail": "Not authenticated"}
            )
        try:
            staff = _load_session_staff(session_cookie)
        except BadSignature:
            return JSONResponse(status_code=401, content={"detail": "Invalid session"})
        if not staff:
            return JSONResponse(
                status_code=401, content={"detail": "Not authenticated"}
            )
        role = staff.get("role", "visitor")
        perms = get_permissions(role)
        return {
            "user": {
                "id": staff["id"],
                "name": staff["name"],
                "email": staff.get("email"),
                "role": role,
                "role_level": staff.get("role_level", 4),
                "permissions": sorted(perms),
            }
        }

    @app.post("/api/auth/logout", include_in_schema=False)
    @app.post("/api/v1/auth/logout")
    def logout():
        response = JSONResponse({"status": "ok"})
        response.delete_cookie(_SESSION_COOKIE)
        return response

    # --- Lab config endpoint (public — frontend reads lab name) ---

    @app.get("/api/config", include_in_schema=False)
    @app.get("/api/v1/config")
    def lab_config():
        cfg = get_settings()
        return {
            "lab_name": cfg.lab_name,
            "lab_subtitle": cfg.lab_subtitle,
            "version": app.version,
            "ocr_model": cfg.ocr_model,
            "extraction_model": cfg.extraction_model,
            "rag_model": cfg.rag_model,
            "ocr_tier": cfg.ocr_tier,
        }

    # --- First-run setup endpoints (no auth required) ---

    def _admin_exists(db) -> bool:
        """Check if any active staff with a password exists."""
        from lab_manager.models.staff import Staff

        return (
            db.scalars(
                select(Staff).where(
                    Staff.password_hash.isnot(None), Staff.is_active.is_(True)
                )
            ).first()
            is not None
        )

    @app.get("/api/setup/status", include_in_schema=False)
    @app.get("/api/v1/setup/status")
    def setup_status(db=Depends(get_db)):
        """Check if initial setup is needed (no admin user with password exists)."""
        return {"needs_setup": not _admin_exists(db)}

    @app.post("/api/setup/complete", include_in_schema=False)
    @app.post("/api/v1/setup/complete")
    @limiter.limit("3/minute")
    def setup_complete(
        request: Request,
        admin_name: str = Body(...),
        admin_email: str = Body(...),
        admin_password: str = Body(...),
        db=Depends(get_db),
    ):
        """First-run setup: create the admin user. Only works when no admin exists."""
        import bcrypt as _bcrypt
        from sqlalchemy.exc import IntegrityError

        from lab_manager.models.staff import Staff

        # Validate inputs before opening DB session
        admin_name = admin_name.strip()
        admin_email = admin_email.strip().lower()
        if not admin_name or len(admin_name) > 200:
            return JSONResponse(
                status_code=422,
                content={"detail": "Name must be between 1 and 200 characters"},
            )
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", admin_email):
            return JSONResponse(
                status_code=422,
                content={"detail": "Invalid email address"},
            )
        if len(admin_email) > 255:
            return JSONResponse(
                status_code=422,
                content={"detail": "Email must be 255 characters or fewer"},
            )
        if len(admin_password) < 8:
            return JSONResponse(
                status_code=422,
                content={"detail": "Password must be at least 8 characters"},
            )
        # bcrypt silently truncates at 72 bytes
        if len(admin_password.encode("utf-8")) > 72:
            return JSONResponse(
                status_code=422,
                content={"detail": "Password must be 72 bytes or fewer"},
            )

        if _admin_exists(db):
            return JSONResponse(
                status_code=409,
                content={"detail": "Setup already completed"},
            )

        # Create or update staff record — first user is always PI
        staff = db.scalars(select(Staff).where(Staff.email == admin_email)).first()
        if staff:
            staff.name = admin_name
            staff.role = "pi"
            staff.role_level = 0
            staff.is_active = True
        else:
            staff = Staff(
                name=admin_name,
                email=admin_email,
                role="pi",
                role_level=0,
                is_active=True,
            )
            db.add(staff)

        staff.password_hash = _bcrypt.hashpw(
            admin_password.encode("utf-8"), _bcrypt.gensalt()
        ).decode("utf-8")

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return JSONResponse(
                status_code=409,
                content={"detail": "Setup already completed"},
            )

        logger.info("Setup complete: admin user created")
        return {
            "status": "ok",
            "message": "Admin account created. You can now sign in.",
        }

    # Register route modules
    from lab_manager.api.routes import (
        alerts,
        analytics,
        ask,
        audit,
        documents,
        email_ingest,
        equipment,
        export,
        import_routes,
        inventory,
        notifications,
        orders,
        products,
        search,
        telemetry,
        vendors,
    )
    from lab_manager.api.routes import barcode  # noqa: E402

    # Auth is handled by auth_middleware — rate limiting via route decorators
    api_router = APIRouter()
    api_router.include_router(
        vendors.router, prefix="/api/v1/vendors", tags=["vendors"]
    )
    api_router.include_router(
        products.router, prefix="/api/v1/products", tags=["products"]
    )
    api_router.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
    api_router.include_router(
        equipment.router, prefix="/api/v1/equipment", tags=["equipment"]
    )
    api_router.include_router(
        inventory.router, prefix="/api/v1/inventory", tags=["inventory"]
    )
    api_router.include_router(
        documents.router, prefix="/api/v1/documents", tags=["documents"]
    )
    api_router.include_router(search.router, prefix="/api/v1/search", tags=["search"])
    api_router.include_router(ask.router, prefix="/api/v1/ask", tags=["ask"])
    api_router.include_router(
        analytics.router, prefix="/api/v1/analytics", tags=["analytics"]
    )
    api_router.include_router(export.router, prefix="/api/v1/export", tags=["export"])
    api_router.include_router(
        import_routes.router, prefix="/api/v1/import", tags=["import"]
    )
    api_router.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    api_router.include_router(alerts.router, prefix="/api/v1/alerts", tags=["alerts"])
    api_router.include_router(
        notifications.router,
        prefix="/api/v1/notifications",
        tags=["notifications"],
    )
    api_router.include_router(
        telemetry.router, prefix="/api/v1/telemetry", tags=["telemetry"]
    )
    api_router.include_router(
        email_ingest.router, prefix="/api/v1/email", tags=["email"]
    )
    api_router.include_router(
        barcode.router, prefix="/api/v1/barcode", tags=["barcode"]
    )

    from lab_manager.api.routes import team

    api_router.include_router(team.router, prefix="/api/v1/team", tags=["team"])
    app.include_router(api_router)

    # --- Apply rate limiting decorators to GET /api/v1/ask endpoint ---
    # Rate limit: 10 requests per minute (same as POST)
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "endpoint"):
            if (
                route.path in ("/api/v1/ask", "/api/v1/ask/")
                and route.methods
                and "GET" in route.methods
            ):
                original_endpoint = route.endpoint
                route.endpoint = limiter.limit("10/minute")(original_endpoint)

    # Serve scan images (protected by auth middleware when auth is enabled)
    if scans_dir and scans_dir.exists():  # pragma: no cover — depends on deployment
        app.mount("/scans", StaticFiles(directory=str(scans_dir)), name="scans")

    # Serve uploaded documents at /uploads/
    upload_path = Path(settings.upload_dir)
    upload_path.mkdir(parents=True, exist_ok=True)
    app.state.upload_dir = upload_path.resolve()
    app.mount(
        "/uploads",
        StaticFiles(directory=str(app.state.upload_dir)),
        name="uploads",
    )

    # Serve device photos
    if devices_dir and devices_dir.exists():  # pragma: no cover — depends on deployment
        app.mount(
            "/lab-devices", StaticFiles(directory=str(devices_dir)), name="devices"
        )

    # Wire up SQLAdmin UI at /admin/
    setup_admin(app, get_engine())

    # Serve frontend static assets and root
    # React SPA build output lives in static/dist/assets/ (JS/CSS bundles).
    # dist/ itself may exist (index.html tracked in git) without the build
    # artifacts, so we check for assets/ to decide SPA vs legacy mode.
    DIST_DIR = STATIC_DIR / "dist"
    SPA_ASSETS = DIST_DIR / "assets"
    if _spa_assets_ready(
        STATIC_DIR
    ):  # pragma: no cover — depends on React build artifacts
        app.mount(
            "/assets",
            StaticFiles(directory=str(SPA_ASSETS)),
            name="dist-assets",
        )

        # Serve icons from static/icons/
        icons_dir = STATIC_DIR / "icons"
        if icons_dir.is_dir():
            app.mount(
                "/icons",
                StaticFiles(directory=str(icons_dir)),
                name="icons",
            )

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

        @app.get("/")
        def index():
            return FileResponse(DIST_DIR / "index.html")

        # SPA catch-all using middleware so it only fires for unmatched paths.
        @app.middleware("http")
        async def spa_middleware(request: Request, call_next):
            response = await call_next(request)
            if (
                response.status_code == 404
                and request.method == "GET"
                and not request.url.path.startswith("/api/")
                and not request.url.path.startswith("/admin/")
                and not request.url.path.startswith("/static/")
                and not request.url.path.startswith("/assets/")
                and not request.url.path.startswith("/scans/")
                and not request.url.path.startswith("/uploads/")
                and request.url.path != "/favicon.svg"
                and request.url.path != "/icons.svg"
            ):
                return FileResponse(DIST_DIR / "index.html")
            return response
    else:
        # Fallback: serve original static files (for dev without React build)
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/")
        def index():
            return FileResponse(STATIC_DIR / "index.html")

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

    # Serve favicon and icons SVGs from dist/ (tracked in git, available in both modes)
    favicon_path = DIST_DIR / "favicon.svg"
    if favicon_path.is_file():

        @app.get("/favicon.svg")
        def favicon():
            return FileResponse(favicon_path, media_type="image/svg+xml")

    icons_svg_path = DIST_DIR / "icons.svg"
    if icons_svg_path.is_file():

        @app.get("/icons.svg")
        def icons_svg():
            return FileResponse(icons_svg_path, media_type="image/svg+xml")

    return app


app = create_app()
