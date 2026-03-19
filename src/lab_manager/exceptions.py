"""Domain exception hierarchy.

All business-logic errors inherit from BusinessError. Each maps to
an HTTP status code via the global exception handler registered in
create_app().

    BusinessError (400)
    ├── NotFoundError (404)
    ├── ValidationError (422)
    ├── ConflictError (409)
    └── ForbiddenError (403)
"""

from __future__ import annotations


class BusinessError(Exception):
    """Base class for all domain/business errors. Maps to HTTP 400."""

    status_code: int = 400

    def __init__(self, message: str = "Bad request"):
        self.message = message
        super().__init__(message)


class NotFoundError(BusinessError):
    """Resource not found. Maps to HTTP 404."""

    status_code: int = 404

    def __init__(self, resource: str = "Resource", id: int | str | None = None):
        detail = f"{resource} not found" if id is None else f"{resource} {id} not found"
        super().__init__(detail)


class ValidationError(BusinessError):
    """Input validation failed. Maps to HTTP 422."""

    status_code: int = 422


class ConflictError(BusinessError):
    """Resource conflict (duplicate, invalid state transition). Maps to HTTP 409."""

    status_code: int = 409


class ForbiddenError(BusinessError):
    """Insufficient permissions. Maps to HTTP 403."""

    status_code: int = 403
