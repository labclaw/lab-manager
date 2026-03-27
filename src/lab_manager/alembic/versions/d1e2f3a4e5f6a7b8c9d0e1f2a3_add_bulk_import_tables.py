"""Add bulk import tables.

Revision ID: d1e2f3a4e5f6a7b8c9d0e1f2a3
Revises: d1e2f3a4e5f6a7b8c9d0e1f2a4
Create Date: 2026-03-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4e5f6a7b8c9d0e1f2a3"
down_revision: Union[str, None] = "d1e2f3a4e5f6a7b8c9d0e1f2a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE import_type AS ENUM ('vendors', 'products', 'inventory')")
    op.execute(
        "CREATE TYPE import_status AS ENUM "
        "('uploading', 'validating', 'preview', 'importing', 'completed', 'failed', 'cancelled')"
    )

    # Create import_jobs table
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "import_type",
            sa.Enum("vendors", "products", "inventory", name="import_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "uploading",
                "validating",
                "preview",
                "importing",
                "completed",
                "failed",
                "cancelled",
                name="import_status",
            ),
            nullable=False,
            server_default="uploading",
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("valid_rows", sa.Integer(), nullable=True),
        sa.Column("imported_rows", sa.Integer(), server_default="0", nullable=True),
        sa.Column("failed_rows", sa.Integer(), server_default="0", nullable=True),
        sa.Column("options", sa.JSON(), server_default="{}", nullable=True),
        sa.Column("preview_data", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("staff.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Indexes for import_jobs (match model __table_args__)
    op.create_index("ix_import_jobs_status", "import_jobs", ["status"])
    op.create_index("ix_import_jobs_created_at", "import_jobs", ["created_at"])

    # Create import_errors table
    op.create_table(
        "import_errors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(100), nullable=True),
        sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index("ix_import_errors_job_id", "import_errors", ["job_id"])
    op.create_index(
        "ix_import_errors_job_row", "import_errors", ["job_id", "row_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_import_errors_job_row", table_name="import_errors")
    op.drop_index("ix_import_errors_job_id", table_name="import_errors")
    op.drop_index("ix_import_jobs_created_at", table_name="import_jobs")
    op.drop_index("ix_import_jobs_status", table_name="import_jobs")
    op.drop_table("import_errors")
    op.drop_table("import_jobs")
    op.execute("DROP TYPE import_status")
    op.execute("DROP TYPE import_type")
