"""Test database models."""

from lab_manager.models.base import AuditMixin


def test_audit_mixin_has_timestamps():
    """AuditMixin should define created_at, updated_at, created_by."""
    fields = {f for f in AuditMixin.model_fields}
    assert "created_at" in fields
    assert "updated_at" in fields
    assert "created_by" in fields


from lab_manager.models.vendor import Vendor
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff
from lab_manager.models.location import StorageLocation


def test_vendor_model():
    v = Vendor(name="Sigma-Aldrich", aliases=["MilliporeSigma", "Merck"])
    assert v.name == "Sigma-Aldrich"
    assert "MilliporeSigma" in v.aliases


def test_product_model():
    p = Product(
        catalog_number="AB1031",
        name="AGGRECAN, RBX MS-50UG",
        vendor_id=1,
    )
    assert p.catalog_number == "AB1031"


def test_staff_model():
    s = Staff(name="Shiqian Shen", email="sshen@mgh.harvard.edu", role="PI")
    assert s.role == "PI"


def test_location_model():
    loc = StorageLocation(name="Freezer -80C #1", temperature=-80, room="CNY 149")
    assert loc.temperature == -80
