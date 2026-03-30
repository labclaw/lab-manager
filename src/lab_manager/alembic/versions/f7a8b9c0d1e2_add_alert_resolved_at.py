"""add_alert_resolved_at

Revision ID: f7a8b9c0d1e2
Revises: d1e2f3a4e5f6a7b8c9d0e1f2a3
Create Date: 2026-03-30 12:39:02.566029

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("resolved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("alerts", "resolved_at")
