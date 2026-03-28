"""add msds fields to product

Revision ID: c1d2e3f4a5b6
Revises: 0c2125df7c3a
Create Date: 2026-03-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str]] = "0c2125df7c3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "hazard_class",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "msds_url",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=True,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "requires_safety_review",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "requires_safety_review")
    op.drop_column("products", "msds_url")
    op.drop_column("products", "hazard_class")
