"""Tests for data integrity: session management, constraints."""

import contextlib

import pytest  # noqa: F401 — used in later tests
from sqlalchemy.exc import IntegrityError  # noqa: F401
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.product import Product  # noqa: F401
from lab_manager.models.vendor import Vendor


def _make_engine():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    import lab_manager.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    return engine


def test_get_db_auto_commits_on_success():
    """get_db() should commit when the block exits without error."""
    import lab_manager.database as db_mod

    engine = _make_engine()
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine)

    original_factory = db_mod._session_factory
    db_mod._session_factory = factory
    try:
        from lab_manager.database import get_db

        gen = get_db()
        session = next(gen)
        session.add(Vendor(name="Test Vendor"))
        # Simulate successful exit
        with contextlib.suppress(StopIteration):
            next(gen)

        # Verify data persisted
        with Session(engine) as check:
            vendor = check.query(Vendor).filter(Vendor.name == "Test Vendor").first()
            assert vendor is not None, "Vendor should be committed"
    finally:
        db_mod._session_factory = original_factory


def test_get_db_rollback_on_exception():
    """get_db() should rollback when the block raises."""
    import lab_manager.database as db_mod

    engine = _make_engine()
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine)

    original_factory = db_mod._session_factory
    db_mod._session_factory = factory
    try:
        from lab_manager.database import get_db

        gen = get_db()
        session = next(gen)
        session.add(Vendor(name="Rollback Vendor"))
        # Simulate exception
        with contextlib.suppress(ValueError):
            gen.throw(ValueError("simulated error"))

        # Verify data NOT persisted
        with Session(engine) as check:
            vendor = check.query(Vendor).filter(Vendor.name == "Rollback Vendor").first()
            assert vendor is None, "Vendor should NOT be committed after error"
    finally:
        db_mod._session_factory = original_factory


# ---------------------------------------------------------------------------
# Task 1.2: Product unique constraint + Decimal stock levels
# ---------------------------------------------------------------------------


def test_product_duplicate_catalog_vendor_rejected(db_session):
    """Same catalog_number + vendor_id should be rejected."""
    v = Vendor(name="DupTest Vendor")
    db_session.add(v)
    db_session.flush()

    p1 = Product(catalog_number="CAT-001", name="Product A", vendor_id=v.id)
    db_session.add(p1)
    db_session.flush()

    p2 = Product(catalog_number="CAT-001", name="Product B", vendor_id=v.id)
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_product_same_catalog_different_vendor_ok(db_session):
    """Same catalog_number but different vendor_id should be allowed."""
    v1 = Vendor(name="Vendor Alpha")
    v2 = Vendor(name="Vendor Beta")
    db_session.add_all([v1, v2])
    db_session.flush()

    p1 = Product(catalog_number="CAT-001", name="Product A", vendor_id=v1.id)
    p2 = Product(catalog_number="CAT-001", name="Product A", vendor_id=v2.id)
    db_session.add_all([p1, p2])
    db_session.flush()  # Should not raise
    assert p1.id != p2.id


# ---------------------------------------------------------------------------
# Task 1.3: Inventory constraints
# ---------------------------------------------------------------------------

from decimal import Decimal  # noqa: E402

from lab_manager.models.inventory import InventoryItem  # noqa: E402


def test_inventory_negative_quantity_rejected(db_session):
    """quantity_on_hand < 0 should be rejected by CHECK constraint."""
    v = Vendor(name="Constraint Vendor")
    db_session.add(v)
    db_session.flush()
    p = Product(catalog_number="C-100", name="Test", vendor_id=v.id)
    db_session.add(p)
    db_session.flush()

    item = InventoryItem(product_id=p.id, quantity_on_hand=Decimal("-1"))
    db_session.add(item)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_inventory_product_id_not_nullable():
    """product_id field should be non-nullable in the model definition."""

    col = InventoryItem.__table__.columns["product_id"]
    assert col.nullable is False


# ---------------------------------------------------------------------------
# Task 1.4: Decimal consistency in inventory service
# ---------------------------------------------------------------------------


def test_consume_decimal_precision(db_session):
    """consume() should handle Decimal comparison without float/Decimal mismatch."""
    from lab_manager.services.inventory import consume

    v = Vendor(name="Decimal Vendor")
    db_session.add(v)
    db_session.flush()
    p = Product(catalog_number="D-001", name="Decimal Test", vendor_id=v.id)
    db_session.add(p)
    db_session.flush()

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=Decimal("1.0000"),
        status="available",
    )
    db_session.add(item)
    db_session.flush()

    # This should NOT raise "insufficient stock" due to float/Decimal mismatch
    consume(item.id, Decimal("1.0000"), "test", None, db_session)
    db_session.flush()

    db_session.refresh(item)
    assert item.quantity_on_hand == Decimal("0")
    assert item.status == "depleted"


def test_adjust_decimal_precision(db_session):
    """adjust() should handle Decimal values correctly."""
    from lab_manager.services.inventory import adjust

    v = Vendor(name="Adjust Vendor")
    db_session.add(v)
    db_session.flush()
    p = Product(catalog_number="A-001", name="Adjust Test", vendor_id=v.id)
    db_session.add(p)
    db_session.flush()

    item = InventoryItem(
        product_id=p.id,
        quantity_on_hand=Decimal("5.0000"),
        status="available",
    )
    db_session.add(item)
    db_session.flush()

    adjust(item.id, Decimal("3.5000"), "cycle count", "test", db_session)
    db_session.flush()

    db_session.refresh(item)
    assert item.quantity_on_hand == Decimal("3.5000")


# ---------------------------------------------------------------------------
# Task 1.6: Product is_active soft delete
# ---------------------------------------------------------------------------


def test_product_has_is_active_field():
    """Product should have an is_active boolean field defaulting to True."""
    assert hasattr(Product, "is_active")
    col = Product.__table__.columns["is_active"]
    assert col.default.arg is True


def test_soft_delete_product(db_session):
    """Deactivating a product should keep it in DB but mark inactive."""
    v = Vendor(name="SoftDel Vendor")
    db_session.add(v)
    db_session.flush()
    p = Product(catalog_number="SD-001", name="Will Deactivate", vendor_id=v.id)
    db_session.add(p)
    db_session.flush()

    p.is_active = False
    db_session.flush()
    db_session.refresh(p)
    assert p.is_active is False
    assert p.id is not None  # Still in DB
