"""Test vendor duplicate name prevention."""

from __future__ import annotations

import pytest

from lab_manager.exceptions import ConflictError
from lab_manager.models.vendor import Vendor


def test_create_vendor_duplicate_name_raises(db_session):
    """Creating a vendor with a duplicate name must raise ConflictError."""
    from lab_manager.api.routes.vendors import create_vendor, VendorCreate

    v1 = Vendor(name="Sigma-Aldrich")
    db_session.add(v1)
    db_session.flush()

    body = VendorCreate(name="Sigma-Aldrich")
    with pytest.raises(ConflictError, match="already exists"):
        create_vendor(body, db_session)
