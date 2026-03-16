"""Tests for data integrity: session management, constraints."""

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.pool import StaticPool

from lab_manager.models.vendor import Vendor


def _make_engine():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
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
        try:
            next(gen)
        except StopIteration:
            pass

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
        try:
            gen.throw(ValueError("simulated error"))
        except ValueError:
            pass

        # Verify data NOT persisted
        with Session(engine) as check:
            vendor = (
                check.query(Vendor).filter(Vendor.name == "Rollback Vendor").first()
            )
            assert vendor is None, "Vendor should NOT be committed after error"
    finally:
        db_mod._session_factory = original_factory
