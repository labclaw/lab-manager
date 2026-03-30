"""Add bulk import tables.

Revision ID: d1e2f3a4e5f6a7b8c9d0e1f2a3
Revises: d0e1f2a3b4c5
Create Date: 2026-03-27

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4e5f6a7b8c9d0e1f2a3"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            CREATE TYPE import_type AS ENUM ('vendors', 'products', 'inventory');
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            CREATE TYPE import_status AS ENUM (
                'uploading', 'validating', 'preview', 'importing', 'completed', 'failed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS import_jobs (
            id SERIAL PRIMARY KEY,
            import_type import_type NOT NULL,
            status import_status NOT NULL DEFAULT 'uploading',
            original_filename VARCHAR(255) NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            total_rows INTEGER,
            valid_rows INTEGER,
            imported_rows INTEGER DEFAULT 0,
            failed_rows INTEGER DEFAULT 0,
            options JSONB DEFAULT '{}',
            preview_data JSONB,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_by_id INTEGER REFERENCES staff(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            created_by VARCHAR(100)
        );
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_import_jobs_status ON import_jobs (status);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_import_jobs_created_at ON import_jobs (created_at);"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS import_errors (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
            row_number INTEGER NOT NULL,
            field VARCHAR(100),
            error_type VARCHAR(50) NOT NULL,
            message VARCHAR(500) NOT NULL,
            raw_data TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_import_errors_job_id ON import_errors (job_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_import_errors_job_row ON import_errors (job_id, row_number);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_import_errors_job_row;")
    op.execute("DROP INDEX IF EXISTS ix_import_errors_job_id;")
    op.execute("DROP INDEX IF EXISTS ix_import_jobs_created_at;")
    op.execute("DROP INDEX IF EXISTS ix_import_jobs_status;")
    op.execute("DROP TABLE IF EXISTS import_errors;")
    op.execute("DROP TABLE IF EXISTS import_jobs;")
    op.execute("DROP TYPE IF EXISTS import_status;")
    op.execute("DROP TYPE IF EXISTS import_type;")
