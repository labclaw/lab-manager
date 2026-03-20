"""Add processing to documents status CHECK constraint.

Revision ID: 4046478f7b78
Revises: b7c9d0e1f2a3
Create Date: 2026-03-19
"""

from alembic import op

revision = "4046478f7b78"
down_revision = "b7c9d0e1f2a3"
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
