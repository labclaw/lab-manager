"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="LabClaw Lab Manager",
        description="Lab inventory management with OCR document intake",
        version="0.1.0",
    )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # Register route modules
    from lab_manager.api.routes import vendors, products, orders, inventory, documents

    app.include_router(vendors.router, prefix="/api/vendors", tags=["vendors"])
    app.include_router(products.router, prefix="/api/products", tags=["products"])
    app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
    app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

    return app
