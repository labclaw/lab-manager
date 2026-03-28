"""Add index on documents.vendor_name for filter queries

Revision ID: a1b2c3d4e5f6
Revises: 9b2c4d6e8f10
Create Date: 2026-03-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str]] = "9b2c4d6e8f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_vendor_name", "documents", ["vendor_name"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_documents_vendor_name", "documents", if_exists=True)
