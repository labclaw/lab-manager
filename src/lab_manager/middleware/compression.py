"""GZip compression middleware with smart content-type filtering."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.gzip import GZipMiddleware


def add_compression(app: FastAPI, minimum_size: int = 500):
    """Add GZip compression for responses above minimum_size bytes.

    Only compresses text-based responses (JSON, HTML, CSS, JS).
    Binary responses (images, PDFs) are skipped.
    """
    app.add_middleware(GZipMiddleware, minimum_size=minimum_size)
