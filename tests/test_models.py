"""Test database models."""

from lab_manager.models.base import AuditMixin


def test_audit_mixin_has_timestamps():
    """AuditMixin should define created_at, updated_at, created_by."""
    fields = {f for f in AuditMixin.model_fields}
    assert "created_at" in fields
    assert "updated_at" in fields
    assert "created_by" in fields
