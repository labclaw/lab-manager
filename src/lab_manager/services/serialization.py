"""Shared JSON serialization helpers for service modules."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def serialize_value(val: Any) -> Any:
    """Convert a Python value to a JSON-safe representation.

    Handles: None, datetime/date, Decimal, numpy int/float, and fallback to str.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (int, float, bool, str)):
        return val
    if isinstance(val, (list, dict)):
        return val
    # numpy int64/float64 guard (avoid hard dependency on numpy)
    type_name = type(val).__name__
    if type_name in ("int64", "int32"):
        return int(val)
    if type_name in ("float64", "float32"):
        return float(val)
    return str(val)
