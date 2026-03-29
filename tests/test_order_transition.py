"""Test order status transitions: pending -> received must be allowed."""

from __future__ import annotations

import pytest

from lab_manager.api.routes.orders import _validate_status_transition
from lab_manager.exceptions import ValidationError
from lab_manager.models.order import OrderStatus


def test_pending_to_received_allowed():
    """pending -> received should not raise."""
    _validate_status_transition(OrderStatus.pending.value, OrderStatus.received.value)


def test_pending_to_shipped_allowed():
    """pending -> shipped should not raise."""
    _validate_status_transition(OrderStatus.pending.value, OrderStatus.shipped.value)


def test_received_to_pending_blocked():
    """received -> pending should raise."""
    with pytest.raises(ValidationError):
        _validate_status_transition(
            OrderStatus.received.value, OrderStatus.pending.value
        )
