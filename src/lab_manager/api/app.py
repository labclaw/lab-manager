"""FastAPI application factory."""

from __future__ import annotations

import hmac
import re
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lab_manager.api.admin import setup_admin
from lab_manager.api.deps import verify_api_key
from lab_manager.config import get_settings
from lab_manager.database import get_engine

# Import to register SQLAlchemy event listeners on module load.
import lab_manager.services.audit as _audit_svc  # noqa: F401

STATIC_DIR = Path(__file__).parent.parent / "static"
SCANS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "shenlab-docs"

# Strip control characters from X-User header to prevent log injection.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_USER_LEN = 100


def create_app() -> FastAPI:
    app = FastAPI(
        title="LabClaw Lab Manager",
        description="Lab inventory management with OCR document intake",
        version="0.1.0",
    )

    # Middleware: set current-user context for audit logging.
    @app.middleware("http")
    async def audit_user_middleware(request: Request, call_next):
        raw = request.headers.get("X-User", "system")
        user = _CONTROL_CHARS.sub("", raw)[:_MAX_USER_LEN]
        _audit_svc.set_current_user(user)
        try:
            response = await call_next(request)
        finally:
            _audit_svc.set_current_user(None)
        return response

    # Middleware: protect /scans/ with API key when auth is enabled.
    @app.middleware("http")
    async def scans_auth_middleware(request: Request, call_next):
        if request.url.path == "/scans" or request.url.path.startswith("/scans/"):
            settings = get_settings()
            if settings.auth_enabled and settings.api_key:
                api_key = request.headers.get("X-Api-Key", "")
                if not hmac.compare_digest(api_key, settings.api_key):
                    return JSONResponse(
                        status_code=401, content={"detail": "Unauthorized"}
                    )
        return await call_next(request)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

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

    api_router = APIRouter(dependencies=[Depends(verify_api_key)])
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

    # Serve scan images (protected by scans_auth_middleware when auth is enabled)
    if SCANS_DIR.exists():
        app.mount("/scans", StaticFiles(directory=str(SCANS_DIR)), name="scans")

    # Wire up SQLAdmin UI at /admin/
    setup_admin(app, get_engine())

    # Serve frontend at root
    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
