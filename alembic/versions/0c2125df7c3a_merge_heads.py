"""merge heads

Revision ID: 0c2125df7c3a
Revises: a0b1c2d3e4f5, a1b2c3d4e5f6, a2b3c4d5e6f7
Create Date: 2026-03-26 12:12:09.806343

"""

from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = "0c2125df7c3a"
down_revision: Union[str, None] = ("a0b1c2d3e4f5", "a1b2c3d4e5f6", "a2b3c4d5e6f7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
