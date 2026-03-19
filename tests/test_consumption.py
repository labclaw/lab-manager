"""Tests for the ConsumptionLog model and ConsumptionAction enum."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.consumption import ConsumptionAction, ConsumptionLog
from lab_manager.models.inventory import InventoryItem
from lab_manager.models.product import Product
from lab_manager.models.staff import Staff  # Needed for created_by in AuditMixin

# --- Fixtures for database setup (similar to existing tests) ---


@pytest.fixture(name="engine")
def engine_fixture():
    """Test engine for in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)  # Create tables for all models
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    """Test database session."""
    with Session(engine) as session:
        yield session


# --- Fixtures for related models ---


@pytest.fixture
def mock_staff(session: Session) -> Staff:
    """A mock staff member for created_by field."""
    staff = Staff(name="Test Creator", email="creator@example.com", role="admin")
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


@pytest.fixture
def mock_product(session: Session) -> Product:
    """A mock product for ConsumptionLog."""
    product = Product(catalog_number="CAT-123", name="Test Product", vendor_id=1)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@pytest.fixture
def mock_inventory_item(session: Session, mock_product: Product) -> InventoryItem:
    """A mock inventory item for ConsumptionLog."""
    inventory = InventoryItem(
        product_id=mock_product.id,
        location_id=1,  # Assume a location exists or is not strictly validated here
        quantity_on_hand=Decimal("100.00"),
        lot_number="L123",
    )
    session.add(inventory)
    session.commit()
    session.refresh(inventory)
    return inventory


# --- Tests for ConsumptionAction enum ---


def test_consumption_action_members():
    """Verify all expected enum members exist and have correct values."""
    assert ConsumptionAction.receive.value == "receive"
    assert ConsumptionAction.consume.value == "consume"
    assert ConsumptionAction.transfer.value == "transfer"
    assert ConsumptionAction.adjust.value == "adjust"
    assert ConsumptionAction.dispose.value == "dispose"
    assert ConsumptionAction.open.value == "open"


def test_consumption_action_type():
    """Verify ConsumptionAction is a string enum."""
    assert isinstance(ConsumptionAction.receive, str)


# --- Tests for ConsumptionLog model ---


def test_consumption_log_creation_happy_path(
    session: Session, mock_inventory_item: InventoryItem, mock_product: Product, mock_staff: Staff
):
    """Test successful creation of a ConsumptionLog entry with all required fields."""
    log = ConsumptionLog(
        inventory_id=mock_inventory_item.id,
        product_id=mock_product.id,
        quantity_used=Decimal("10.50"),
        quantity_remaining=Decimal("89.50"),
        consumed_by=mock_staff.name,
        action=ConsumptionAction.consume,
        purpose="Experiment A",
        created_by=mock_staff.name,  # From AuditMixin
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    assert log.id is not None
    assert log.inventory_id == mock_inventory_item.id
    assert log.product_id == mock_product.id
    assert log.quantity_used == Decimal("10.50")
    assert log.quantity_remaining == Decimal("89.50")
    assert log.consumed_by == mock_staff.name
    assert log.action == ConsumptionAction.consume
    assert log.purpose == "Experiment A"
    assert log.created_by == mock_staff.name
    assert isinstance(log.created_at, datetime)
    assert isinstance(log.updated_at, datetime)


def test_consumption_log_creation_without_optional_fields(
    session: Session, mock_inventory_item: InventoryItem, mock_staff: Staff
):
    """Test creation of a ConsumptionLog entry without optional product_id and purpose."""
    log = ConsumptionLog(
        inventory_id=mock_inventory_item.id,
        quantity_used=Decimal("5.00"),
        quantity_remaining=Decimal("95.00"),
        consumed_by=mock_staff.name,
        action=ConsumptionAction.adjust,
        created_by=mock_staff.name,
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    assert log.id is not None
    assert log.product_id is None
    assert log.purpose is None


def test_consumption_log_quantity_types():
    """Ensure quantity_used and quantity_remaining are Decimal types."""
    log = ConsumptionLog(
        inventory_id=1,
        quantity_used=Decimal("1.2345"),
        quantity_remaining=Decimal("98.7655"),
        consumed_by="user",
        action=ConsumptionAction.receive,
        created_by="user",
    )
    assert isinstance(log.quantity_used, Decimal)
    assert isinstance(log.quantity_remaining, Decimal)
    assert log.quantity_used == Decimal("1.2345")
    assert log.quantity_remaining == Decimal("98.7655")


def test_consumption_log_action_enum_validation(
    session: Session, mock_inventory_item: InventoryItem, mock_staff: Staff
):
    """Test that only valid enum actions can be set."""
    # This primarily relies on the CheckConstraint in the database,
    # but we can check if SQLModel/Pydantic catches it (it usually doesn't for SQLModel fields directly).
    # For now, we ensure valid actions work.
    for action in ConsumptionAction:
        log = ConsumptionLog(
            inventory_id=mock_inventory_item.id,
            quantity_used=Decimal("1.00"),
            quantity_remaining=Decimal("99.00"),
            consumed_by=mock_staff.name,
            action=action,
            created_by=mock_staff.name,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        assert log.action == action
        session.delete(log)
        session.commit()


def test_consumption_log_relationships(
    session: Session, mock_inventory_item: InventoryItem, mock_product: Product, mock_staff: Staff
):
    """Test that relationships are correctly established."""
    log = ConsumptionLog(
        inventory_id=mock_inventory_item.id,
        product_id=mock_product.id,
        quantity_used=Decimal("1.00"),
        quantity_remaining=Decimal("99.00"),
        consumed_by=mock_staff.name,
        action=ConsumptionAction.consume,
        created_by=mock_staff.name,
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    # Reload inventory_item and product to check back_populates
    session.refresh(mock_inventory_item)
    session.refresh(mock_product)

    assert log.inventory_item.id == mock_inventory_item.id
    assert log.product.id == mock_product.id
    assert len(mock_inventory_item.consumption_logs) == 1
    assert mock_inventory_item.consumption_logs[0].id == log.id
    assert len(mock_product.consumption_logs) == 1
    assert mock_product.consumption_logs[0].id == log.id

