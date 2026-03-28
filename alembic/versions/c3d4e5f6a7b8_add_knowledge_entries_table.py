"""add knowledge_entries table

Revision ID: c3d4e5f6a7b8
Revises: 0c2125df7c3a
Create Date: 2026-03-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str]] = "0c2125df7c3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "title", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False
        ),
        sa.Column(
            "category",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
            server_default="general",
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column(
            "source_type",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.Column(
            "source_url",
            sqlmodel.sql.sqltypes.AutoString(length=2000),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_by", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.CheckConstraint(
            "category IN ('sop','safety','equipment_manual','protocol','troubleshooting','general')",
            name="ck_knowledge_entries_category",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_entries_title", "knowledge_entries", ["title"])
    op.create_index("ix_knowledge_entries_category", "knowledge_entries", ["category"])
    op.create_index(
        "ix_knowledge_entries_is_deleted", "knowledge_entries", ["is_deleted"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_entries_is_deleted")
    op.drop_index("ix_knowledge_entries_category")
    op.drop_index("ix_knowledge_entries_title")
    op.drop_table("knowledge_entries")
