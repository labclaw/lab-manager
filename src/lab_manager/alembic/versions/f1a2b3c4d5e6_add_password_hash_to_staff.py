"""Add password_hash column to staff table.

Revision ID: f1a2b3c4d5e6
Revises: f6a7b8c9d0e1
Create Date: 2026-03-16
"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("staff", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("staff", "password_hash")
