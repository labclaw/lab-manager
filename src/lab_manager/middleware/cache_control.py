"""Cache-Control header middleware for HTTP caching."""

from __future__ import annotations

import hashlib
import time

from fastapi import Request
from starlette.responses import Response

# Cache policies by path prefix
_CACHE_POLICIES = {
    "/assets/": "public, max-age=31536000, immutable",  # Built JS/CSS: 1 year
    "/icons/": "public, max-age=86400",  # Icons: 1 day
    "/static/": "public, max-age=3600",  # Static files: 1 hour
    "/favicon.svg": "public, max-age=86400",
    "/manifest.json": "public, max-age=3600",
}

# API responses: short cache with revalidation
_API_CACHE_TTL = {
    "/api/v1/analytics/": 300,  # 5 min
    "/api/v1/search/": 60,  # 1 min
    "/api/config": 3600,  # 1 hour
    "/api/health": 10,  # 10 sec
}


async def cache_control_middleware(request: Request, call_next) -> Response:
    """Add Cache-Control and ETag headers based on route."""
    response = await call_next(request)

    path = request.url.path

    # Static assets: aggressive caching
    for prefix, policy in _CACHE_POLICIES.items():
        if path.startswith(prefix) or path == prefix:
            response.headers["Cache-Control"] = policy
            return response

    # API GET responses: conditional caching
    if request.method == "GET":
        for prefix, ttl in _API_CACHE_TTL.items():
            if path.startswith(prefix):
                response.headers["Cache-Control"] = (
                    f"public, max-age={ttl}, stale-while-revalidate={ttl * 2}"
                )
                # Add weak ETag for conditional requests
                if hasattr(response, "body"):
                    etag = hashlib.md5(
                        f"{path}:{time.time() // ttl}".encode()
                    ).hexdigest()[:16]
                    response.headers["ETag"] = f'W/"{etag}"'
                return response

    # Mutations: no cache
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        response.headers["Cache-Control"] = "no-store"

    return response
