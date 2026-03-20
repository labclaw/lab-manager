"""Add processing to documents status CHECK constraint.

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-03-19
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending','processing','extracted','needs_review','approved','rejected','ocr_failed','deleted')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_status",
        "documents",
        "status IN ('pending','extracted','needs_review','approved','rejected','ocr_failed','deleted')",
    )
