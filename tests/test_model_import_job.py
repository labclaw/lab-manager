"""Unit tests for ImportJob, ImportErrorRecord models and related enums."""

from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from lab_manager.models.import_job import (
    ImportErrorRecord,
    ImportJob,
    ImportStatus,
    ImportType,
)
from lab_manager.models.staff import Staff


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def mock_staff(session: Session) -> Staff:
    staff = Staff(name="Importer", email="importer@example.com", role="admin")
    session.add(staff)
    session.commit()
    session.refresh(staff)
    return staff


# --- ImportType enum ---


class TestImportType:
    def test_enum_members(self):
        assert ImportType.products.value == "products"
        assert ImportType.vendors.value == "vendors"
        assert ImportType.inventory.value == "inventory"

    def test_enum_is_string(self):
        for member in ImportType:
            assert isinstance(member, str)

    def test_enum_member_count(self):
        assert len(ImportType) == 3


# --- ImportStatus enum ---


class TestImportStatus:
    def test_enum_members(self):
        assert ImportStatus.uploading.value == "uploading"
        assert ImportStatus.validating.value == "validating"
        assert ImportStatus.preview.value == "preview"
        assert ImportStatus.importing.value == "importing"
        assert ImportStatus.completed.value == "completed"
        assert ImportStatus.failed.value == "failed"
        assert ImportStatus.cancelled.value == "cancelled"

    def test_enum_is_string(self):
        for member in ImportStatus:
            assert isinstance(member, str)

    def test_enum_member_count(self):
        assert len(ImportStatus) == 7


# --- ImportJob model ---


class TestImportJob:
    def test_create_with_required_fields(self, session, mock_staff):
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="products.csv",
            file_size_bytes=1024,
            file_hash="a" * 64,
            created_by_id=mock_staff.id,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.id is not None
        assert job.import_type == ImportType.products
        assert job.original_filename == "products.csv"
        assert job.file_size_bytes == 1024
        assert job.file_hash == "a" * 64

    def test_default_status_is_uploading(self, session):
        job = ImportJob(
            import_type=ImportType.vendors,
            original_filename="vendors.csv",
            file_size_bytes=512,
            file_hash="b" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.status == ImportStatus.uploading

    def test_default_progress_counts(self, session):
        job = ImportJob(
            import_type=ImportType.inventory,
            original_filename="inv.csv",
            file_size_bytes=2048,
            file_hash="c" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.imported_rows == 0
        assert job.failed_rows == 0
        assert job.total_rows is None
        assert job.valid_rows is None

    def test_default_options_is_empty_dict(self, session):
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="test.csv",
            file_size_bytes=100,
            file_hash="d" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.options == {}

    def test_timing_fields_default_none(self, session):
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="t.csv",
            file_size_bytes=10,
            file_hash="e" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.started_at is None
        assert job.completed_at is None

    def test_preview_data_can_be_set(self, session):
        preview = [{"name": "Product A", "catalog": "CA-001"}]
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="p.csv",
            file_size_bytes=50,
            file_hash="f" * 64,
            preview_data=preview,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert len(job.preview_data) == 1
        assert job.preview_data[0]["name"] == "Product A"

    def test_progress_fields_update(self, session):
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="g.csv",
            file_size_bytes=200,
            file_hash="g" * 64,
            total_rows=100,
            valid_rows=95,
            imported_rows=90,
            failed_rows=5,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.total_rows == 100
        assert job.valid_rows == 95
        assert job.imported_rows == 90
        assert job.failed_rows == 5

    def test_audit_mixin_fields_present(self):
        fields = {f for f in ImportJob.model_fields}
        assert "created_at" in fields
        assert "updated_at" in fields
        assert "created_by" in fields

    def test_status_transition_to_completed(self, session):
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="h.csv",
            file_size_bytes=300,
            file_hash="h" * 64,
            status=ImportStatus.completed,
            completed_at=datetime(2026, 3, 27, 12, 0, 0),
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.status == ImportStatus.completed
        assert job.completed_at == datetime(2026, 3, 27, 12, 0, 0)


# --- ImportErrorRecord model ---


class TestImportErrorRecord:
    def test_create_error_record(self, session):
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="err.csv",
            file_size_bytes=100,
            file_hash="i" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        error = ImportErrorRecord(
            job_id=job.id,
            row_number=3,
            field="catalog_number",
            error_type="validation",
            message="Catalog number is required",
            raw_data='{"name":"X","catalog_number":""}',
        )
        session.add(error)
        session.commit()
        session.refresh(error)

        assert error.id is not None
        assert error.job_id == job.id
        assert error.row_number == 3
        assert error.error_type == "validation"
        assert error.message == "Catalog number is required"

    def test_error_optional_field_is_none(self, session):
        job = ImportJob(
            import_type=ImportType.vendors,
            original_filename="v.csv",
            file_size_bytes=50,
            file_hash="j" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        error = ImportErrorRecord(
            job_id=job.id,
            row_number=1,
            error_type="duplicate",
            message="Row already exists",
        )
        session.add(error)
        session.commit()
        session.refresh(error)

        assert error.field is None
        assert error.raw_data is None

    def test_multiple_errors_per_job(self, session):
        job = ImportJob(
            import_type=ImportType.inventory,
            original_filename="multi.csv",
            file_size_bytes=500,
            file_hash="k" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        for i in range(5):
            error = ImportErrorRecord(
                job_id=job.id,
                row_number=i + 1,
                error_type="validation",
                message=f"Error on row {i + 1}",
            )
            session.add(error)
        session.commit()

        from sqlmodel import select

        errors = session.exec(
            select(ImportErrorRecord).where(ImportErrorRecord.job_id == job.id)
        ).all()
        assert len(errors) == 5

    def test_error_type_values(self, session):
        """Verify various error_type strings can be stored."""
        job = ImportJob(
            import_type=ImportType.products,
            original_filename="types.csv",
            file_size_bytes=100,
            file_hash="l" * 64,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        for etype in ["validation", "duplicate", "not_found", "system"]:
            error = ImportErrorRecord(
                job_id=job.id,
                row_number=1,
                error_type=etype,
                message=f"{etype} error",
            )
            session.add(error)
        session.commit()

        from sqlmodel import select

        errors = session.exec(
            select(ImportErrorRecord).where(ImportErrorRecord.job_id == job.id)
        ).all()
        types = {e.error_type for e in errors}
        assert types == {"validation", "duplicate", "not_found", "system"}
